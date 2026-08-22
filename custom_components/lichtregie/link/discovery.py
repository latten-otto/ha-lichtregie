"""Die Anlage aus Home Assistant einlesen.

Erzeugt einen Vorschlag: Zonen aus den Bereichen, Lichtkreise aus den
Leuchten, Rollen aus Namen und Fähigkeiten, dazu die Sensorik und alle
Bedienelemente. Nichts davon wird stillschweigend übernommen — der Vorschlag
geht in die Oberfläche, der Bediener bestätigt.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import dt as dt_util

from ..const import DEFAULT_CURVE, ROLE_AMBIENT, ROLE_EFFECT, ROLE_NIGHT
from ..core.model import Circuit, ControlPoint, Fixture, Installation, Zone
from ..core.naming import (
    KIND_DEFAULTS,
    guess_kind,
    guess_role,
    is_group,
    is_room_lighting,
)

_LOGGER = logging.getLogger(__name__)

def read_capabilities(state) -> dict[str, Any]:
    """Fähigkeiten einer Leuchte aus ihrem Zustand ablesen."""
    attrs = state.attributes if state else {}
    modes = set(attrs.get("supported_color_modes") or [])
    color = bool(modes & {"hs", "xy", "rgb", "rgbw", "rgbww"})
    color_temp = "color_temp" in modes or color
    dimmable = bool(modes - {"onoff"}) or "brightness" in attrs
    # Bit 0 der supported_features bedeutet Übergangszeit.
    features = int(attrs.get("supported_features") or 0)
    return {
        "dimmable": dimmable,
        "color": color,
        "color_temp": color_temp,
        "min_kelvin": attrs.get("min_color_temp_kelvin"),
        "max_kelvin": attrs.get("max_color_temp_kelvin"),
        "supports_transition": bool(features & 32) or dimmable,
    }


# --------------------------------------------------------------------------
# Sensorbewertung
# --------------------------------------------------------------------------


async def rate_lux_sensor(hass: HomeAssistant, entity_id: str) -> tuple[str, dict]:
    """Bewertet einen Helligkeitssensor anhand seiner Historie.

    Rückgabe ist ``regelfaehig``, ``momentaufnahme`` oder ``tot`` mit den
    Kennzahlen, auf denen die Einstufung beruht. Ein Sensor, der in zwei
    Tagen einen einzigen Wert meldet, taugt nicht als Regelgröße — das ist
    kein theoretischer Fall, sondern der Normalzustand mancher Melder.
    """
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable"):
        return "tot", {"grund": "kein Messwert"}

    try:
        from homeassistant.components.recorder import get_instance, history
    except ImportError:  # Recorder abgeschaltet
        return "momentaufnahme", {"grund": "keine Historie verfügbar"}

    start = dt_util.utcnow() - timedelta(hours=48)

    def _fetch():
        return history.state_changes_during_period(
            hass, start, dt_util.utcnow(), entity_id, no_attributes=True
        )

    try:
        rows = await get_instance(hass).async_add_executor_job(_fetch)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Historie für %s nicht lesbar: %s", entity_id, err)
        return "momentaufnahme", {"grund": "Historie nicht lesbar"}

    values = []
    for item in rows.get(entity_id, []):
        try:
            values.append(float(item.state))
        except (ValueError, TypeError):
            continue

    stats = {
        "messwerte": len(values),
        "min": round(min(values), 1) if values else None,
        "max": round(max(values), 1) if values else None,
    }

    if len(values) < 5:
        return "tot", stats
    spread = (max(values) - min(values)) if values else 0
    if len(values) < 100 or spread < 20:
        return "momentaufnahme", stats
    return "regelfaehig", stats


# --------------------------------------------------------------------------
# Bedienelemente
# --------------------------------------------------------------------------

_BUTTON_TRIGGER = re.compile(r"remote_button|button|press|push", re.I)
_DECONZ_GROUP_MODEL = "deconz group"


async def discover_controls(hass: HomeAssistant) -> list[ControlPoint]:
    """Findet alle Taster, Wandsender und Eingänge — herstellerunabhängig."""
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    areas = ar.async_get(hass)
    out: list[ControlPoint] = []

    # Namen der deCONZ-Gruppen merken, um Direktbindungen zu erkennen.
    group_names = [
        (device.name_by_user or device.name or "")
        for device in devices.devices.values()
        if _DECONZ_GROUP_MODEL in (device.model or "").lower()
    ]

    # 1) Geräte mit Tastenauslösern (deCONZ, ZHA, Hue …)
    try:
        from homeassistant.components.device_automation import (
            async_get_device_automations,
            DeviceAutomationType,
        )

        found = await async_get_device_automations(
            hass,
            DeviceAutomationType.TRIGGER,
            [d.id for d in devices.devices.values()],
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Geräteauslöser nicht lesbar: %s", err)
        found = {}

    for device_id, triggers in found.items():
        button_triggers = [
            t for t in triggers if _BUTTON_TRIGGER.search(str(t.get("type", "")))
        ]
        if not button_triggers:
            continue
        device = devices.async_get(device_id)
        if device is None:
            continue
        name = device.name_by_user or device.name or device_id
        model = device.model or ""
        buttons = len({t.get("subtype") for t in button_triggers if t.get("subtype")})

        prefix = model.split()[0] if model else ""
        bound = [g for g in group_names if prefix and g.startswith(prefix)]

        out.append(
            ControlPoint(
                id=f"dev_{device_id[:8]}",
                name=name,
                source="device_trigger",
                device_id=device_id,
                model=f"{device.manufacturer or ''} {model}".strip(),
                buttons=max(1, buttons),
                zone_id=(
                    areas.async_get_area(device.area_id).id
                    if device.area_id and areas.async_get_area(device.area_id)
                    else None
                ),
                direct_bound=bool(bound),
                direct_groups=bound,
            )
        )

    # 2) Ereignis-Entitäten (Shelly-Eingänge, moderne Integrationen)
    for entry in entities.entities.values():
        if entry.domain != "event" or entry.disabled_by:
            continue
        state = hass.states.get(entry.entity_id)
        types = list((state.attributes.get("event_types") if state else []) or [])
        # Nur Bedienereignisse, keine Klingel-, Kamera- oder Backupereignisse.
        if not any(_BUTTON_TRIGGER.search(t) for t in types):
            continue
        out.append(
            ControlPoint(
                id=f"ev_{entry.entity_id.split('.', 1)[1][:24]}",
                name=state.name if state else entry.entity_id,
                source="event_entity",
                entity_id=entry.entity_id,
                model="Ereignis-Entität",
                buttons=1,
                zone_id=entry.area_id,
            )
        )

    # 3) Reine Kontakteingänge, die sonst niemand als Taster erkennt
    for entry in entities.entities.values():
        if entry.domain != "binary_sensor" or entry.disabled_by:
            continue
        name = (entry.name or entry.original_name or entry.entity_id).lower()
        if not ("taster" in name or "eingang" in name or "input" in name):
            continue
        if any(c.entity_id == entry.entity_id for c in out):
            continue
        out.append(
            ControlPoint(
                id=f"bin_{entry.entity_id.split('.', 1)[1][:24]}",
                name=entry.name or entry.original_name or entry.entity_id,
                source="binary_sensor",
                entity_id=entry.entity_id,
                model="Kontakteingang",
                buttons=1,
                zone_id=entry.area_id,
            )
        )

    return out


# --------------------------------------------------------------------------
# Zonen
# --------------------------------------------------------------------------


async def discover(hass: HomeAssistant, rate_sensors: bool = True) -> Installation:
    """Liest die gesamte Anlage ein."""
    areas = ar.async_get(hass)
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    installation = Installation()

    by_area: dict[str, list[str]] = {}
    for entry in entities.entities.values():
        if entry.disabled_by:
            continue
        area_id = entry.area_id
        if area_id is None and entry.device_id:
            device = devices.async_get(entry.device_id)
            area_id = device.area_id if device else None
        if area_id is None:
            continue
        by_area.setdefault(area_id, []).append(entry.entity_id)

    for area in areas.async_list_areas():
        members = by_area.get(area.id, [])
        lights = [e for e in members if e.startswith("light.")]
        if not lights:
            continue

        kind = guess_kind(area.name)
        defaults = KIND_DEFAULTS.get(kind, KIND_DEFAULTS["wohnraum"])

        zone = Zone(
            id=area.id,
            name=area.name,
            kind=kind,
            area_id=area.id,
            setpoint_lux=defaults["setpoint_lux"],
            lux_on_below=defaults["on_below"],
            lux_off_above=defaults["off_above"],
            linger=defaults["linger"],
        )

        # Lichtkreise: je Leuchte einer, Zusammenfassen ist Sache des Bedieners.
        index = 0
        for entity_id in sorted(lights):
            state = hass.states.get(entity_id)
            name = state.name if state else entity_id

            entry = entities.async_get(entity_id)
            device = (
                devices.async_get(entry.device_id)
                if entry and entry.device_id
                else None
            )
            if is_group(state, device):
                _LOGGER.debug("%s übersprungen: ist eine Gruppe", entity_id)
                continue

            caps = read_capabilities(state)
            fixture = Fixture(
                entity_id=entity_id,
                name=name,
                curve=DEFAULT_CURVE,
                **caps,
            )
            role = guess_role(name, caps)
            fixture.night_capable = role in (ROLE_NIGHT, ROLE_AMBIENT)

            index += 1
            room_light = is_room_lighting(name)
            zone.circuits.append(
                Circuit(
                    id=f"k{index}",
                    name=name,
                    role=role if room_light else ROLE_EFFECT,
                    fixtures=[fixture],
                    # Keine Raumbeleuchtung: eingelesen, aber abgeschaltet,
                    # damit keine Szene sie mitschaltet.
                    enabled=room_light,
                )
            )

        # Sensorik
        for entity_id in members:
            state = hass.states.get(entity_id)
            if state is None:
                continue
            device_class = state.attributes.get("device_class")
            if entity_id.startswith("binary_sensor.") and device_class in (
                "motion",
                "occupancy",
                "presence",
            ):
                zone.presence_entities.append(entity_id)
            elif entity_id.startswith("binary_sensor.") and device_class in (
                "door",
                "opening",
            ):
                zone.door_entities.append(entity_id)
            elif entity_id.startswith("media_player."):
                zone.media_entities.append(entity_id)
            elif (
                entity_id.startswith("sensor.")
                and device_class == "illuminance"
                and zone.lux_entity is None
            ):
                zone.lux_entity = entity_id

        if zone.lux_entity and rate_sensors:
            quality, _stats = await rate_lux_sensor(hass, zone.lux_entity)
            zone.lux_quality = quality

        installation.zones.append(zone)

    installation.controls = await discover_controls(hass)
    return installation
