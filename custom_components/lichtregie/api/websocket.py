"""Schnittstelle für das Panel.

Eigene Kommandos über die bestehende, bereits angemeldete WebSocket-
Verbindung des Frontends. Dadurch braucht das Panel keine zweite
Anmeldung und funktioniert über jeden vorhandenen Fernzugriff.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from ..const import DOMAIN
from ..core.bindings import TEMPLATES, apply_template, describe
from ..core.daylight import DEFAULT_CURVES, KIND_TO_CURVE
from ..core.model import Binding, ControlPoint, Installation, Scene, Zone
from ..core.scenes import suggest_scenes


def _data(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data[DOMAIN]


def _engine(hass: HomeAssistant):
    return _data(hass)["engine"]


def _store(hass: HomeAssistant):
    return _data(hass)["store"]


@callback
def async_register(hass: HomeAssistant) -> None:
    """Meldet alle Kommandos an."""
    for handler in (
        ws_get_config,
        ws_set_zone,
        ws_set_control,
        ws_discover,
        ws_state,
        ws_subscribe,
        ws_apply_scene,
        ws_preview,
        ws_suggest,
        ws_zone_off,
        ws_zone_next,
        ws_release_layer,
        ws_journal,
        ws_set_mode,
        ws_revisions,
        ws_rollback,
        ws_binding_set,
        ws_binding_delete,
        ws_templates,
        ws_template_apply,
        ws_calibrate,
        ws_curves,
        ws_zone_settings,
        ws_scene_set,
        ws_scene_delete,
        ws_scene_snapshot,
    ):
        websocket_api.async_register_command(hass, handler)


# --------------------------------------------------------------------------
# Konfiguration
# --------------------------------------------------------------------------


@websocket_api.websocket_command({vol.Required("type"): "lichtregie/config/get"})
@callback
def ws_get_config(hass, connection, msg) -> None:
    installation: Installation = _store(hass).installation
    connection.send_result(msg["id"], installation.to_dict())


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/zone/set",
        vol.Required("zone"): dict,
        vol.Optional("label"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_zone(hass, connection, msg) -> None:
    """Legt eine Zone an oder ersetzt sie."""
    store = _store(hass)
    zone = Zone.from_dict(msg["zone"])
    zones = store.installation.zones
    for index, existing in enumerate(zones):
        if existing.id == zone.id:
            zones[index] = zone
            break
    else:
        zones.append(zone)
    await store.save(label=msg.get("label", f"Zone {zone.name}"))
    _engine(hass).rebuild()
    connection.send_result(msg["id"], {"ok": True, "version": store.installation.version})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/control/set",
        vol.Required("control"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_control(hass, connection, msg) -> None:
    """Speichert die Belegung eines Bedienelements."""
    store = _store(hass)
    control = ControlPoint.from_dict(msg["control"])
    controls = store.installation.controls
    for index, existing in enumerate(controls):
        if existing.id == control.id:
            controls[index] = control
            break
    else:
        controls.append(control)
    await store.save(label=f"Bedienelement {control.name}")
    _engine(hass).rebuild()
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/discover",
        vol.Optional("merge", default=True): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_discover(hass, connection, msg) -> None:
    """Liest die Anlage ein und liefert den Vorschlag.

    Ohne ``merge`` wird nur vorgeschlagen, nichts gespeichert.
    """
    from ..link.discovery import discover

    found = await discover(hass)
    if msg.get("merge"):
        store = _store(hass)
        known_zones = {z.id for z in store.installation.zones}
        known_controls = {c.id for c in store.installation.controls}
        added_zones = [z for z in found.zones if z.id not in known_zones]
        added_controls = [c for c in found.controls if c.id not in known_controls]
        store.installation.zones.extend(added_zones)
        store.installation.controls.extend(added_controls)
        if added_zones or added_controls:
            await store.save(label="Anlage eingelesen")
            _engine(hass).rebuild()
        connection.send_result(
            msg["id"],
            {
                "neue_zonen": [z.name for z in added_zones],
                "neue_bedienelemente": [c.name for c in added_controls],
                "installation": store.installation.to_dict(),
            },
        )
        return

    connection.send_result(msg["id"], found.to_dict())


# --------------------------------------------------------------------------
# Zustand
# --------------------------------------------------------------------------


@websocket_api.websocket_command({vol.Required("type"): "lichtregie/state"})
@callback
def ws_state(hass, connection, msg) -> None:
    connection.send_result(msg["id"], _engine(hass).overview())


@websocket_api.websocket_command({vol.Required("type"): "lichtregie/subscribe"})
@callback
def ws_subscribe(hass, connection, msg) -> None:
    """Schickt Zustandsänderungen und Protokolleinträge an das Panel."""
    engine = _engine(hass)
    journal = _data(hass)["journal"]

    @callback
    def on_change(kind: str, payload: dict) -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], {"art": kind, "daten": payload})
        )

    @callback
    def on_entry(entry) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg["id"], {"art": "protokoll", "daten": entry.to_dict()}
            )
        )

    unsub_engine = engine.subscribe(on_change)
    unsub_journal = journal.subscribe(on_entry)

    @callback
    def unsubscribe() -> None:
        unsub_engine()
        unsub_journal()

    connection.subscriptions[msg["id"]] = unsubscribe
    connection.send_result(msg["id"])


# --------------------------------------------------------------------------
# Befehle
# --------------------------------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/scene/apply",
        vol.Required("zone_id"): str,
        vol.Required("scene_id"): str,
    }
)
@websocket_api.async_response
async def ws_apply_scene(hass, connection, msg) -> None:
    ok = await _engine(hass).apply_scene(msg["zone_id"], msg["scene_id"])
    connection.send_result(msg["id"], {"ok": ok})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/scene/preview",
        vol.Required("zone_id"): str,
        vol.Required("levels"): {str: vol.Coerce(float)},
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_preview(hass, connection, msg) -> None:
    ok = await _engine(hass).preview(msg["zone_id"], msg["levels"])
    connection.send_result(msg["id"], {"ok": ok})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/scene/suggest",
        vol.Required("zone_id"): str,
        vol.Optional("apply", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_suggest(hass, connection, msg) -> None:
    store = _store(hass)
    zone = store.installation.zone(msg["zone_id"])
    if zone is None:
        connection.send_error(msg["id"], "unbekannt", "Zone nicht gefunden")
        return
    proposals = suggest_scenes(zone)
    if msg.get("apply") and proposals:
        zone.scenes.extend(proposals)
        await store.save(label=f"Szenen für {zone.name}")
        _engine(hass).rebuild()
    connection.send_result(
        msg["id"], {"szenen": [s.to_dict() for s in proposals]}
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "lichtregie/zone/off", vol.Required("zone_id"): str}
)
@websocket_api.async_response
async def ws_zone_off(hass, connection, msg) -> None:
    connection.send_result(
        msg["id"], {"ok": await _engine(hass).turn_off(msg["zone_id"])}
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "lichtregie/zone/next", vol.Required("zone_id"): str}
)
@websocket_api.async_response
async def ws_zone_next(hass, connection, msg) -> None:
    connection.send_result(
        msg["id"], {"ok": await _engine(hass).next_scene(msg["zone_id"])}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/layer/release",
        vol.Required("zone_id"): str,
        vol.Required("layer"): int,
    }
)
@websocket_api.async_response
async def ws_release_layer(hass, connection, msg) -> None:
    connection.send_result(
        msg["id"],
        {"ok": await _engine(hass).release_layer(msg["zone_id"], msg["layer"])},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/mode",
        vol.Required("mode"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_mode(hass, connection, msg) -> None:
    store = _store(hass)
    store.installation.mode = msg["mode"]
    await store.save(label=f"Betriebsart {msg['mode']}")
    connection.send_result(msg["id"], {"ok": True})


# --------------------------------------------------------------------------
# Protokoll und Fassungen
# --------------------------------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/journal",
        vol.Optional("zone_id"): str,
        vol.Optional("limit", default=200): int,
    }
)
@callback
def ws_journal(hass, connection, msg) -> None:
    journal = _data(hass)["journal"]
    connection.send_result(
        msg["id"],
        {"eintraege": journal.recent(msg.get("zone_id"), msg.get("limit", 200))},
    )


@websocket_api.websocket_command({vol.Required("type"): "lichtregie/revisions"})
@callback
def ws_revisions(hass, connection, msg) -> None:
    connection.send_result(msg["id"], {"fassungen": _store(hass).revisions()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/rollback",
        vol.Required("version"): int,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_rollback(hass, connection, msg) -> None:
    ok = await _store(hass).rollback(msg["version"])
    if ok:
        _engine(hass).rebuild()
    connection.send_result(msg["id"], {"ok": ok})


# --------------------------------------------------------------------------
# Bindungen
# --------------------------------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/binding/set",
        vol.Required("binding"): dict,
        vol.Optional("control_id"): str,
        vol.Optional("zone_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_binding_set(hass, connection, msg) -> None:
    """Legt eine Bindung an oder ersetzt sie — am Taster oder an der Zone."""
    store = _store(hass)
    binding = Binding.from_dict(msg["binding"])

    if msg.get("control_id"):
        owner = store.installation.control(msg["control_id"])
        label = f"Bindung an {owner.name}" if owner else "Bindung"
    elif msg.get("zone_id"):
        owner = store.installation.zone(msg["zone_id"])
        label = f"Bindung in {owner.name}" if owner else "Bindung"
    else:
        connection.send_error(msg["id"], "fehlt", "control_id oder zone_id angeben")
        return

    if owner is None:
        connection.send_error(msg["id"], "unbekannt", "Ziel nicht gefunden")
        return

    for index, existing in enumerate(owner.bindings):
        if existing.id == binding.id:
            owner.bindings[index] = binding
            break
    else:
        owner.bindings.append(binding)

    await store.save(label=label)
    _engine(hass).rebuild()
    connection.send_result(msg["id"], {"ok": True, "text": describe(binding)})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/binding/delete",
        vol.Required("binding_id"): str,
        vol.Optional("control_id"): str,
        vol.Optional("zone_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_binding_delete(hass, connection, msg) -> None:
    store = _store(hass)
    owner = (
        store.installation.control(msg["control_id"])
        if msg.get("control_id")
        else store.installation.zone(msg.get("zone_id", ""))
    )
    if owner is None:
        connection.send_error(msg["id"], "unbekannt", "Ziel nicht gefunden")
        return
    before = len(owner.bindings)
    owner.bindings = [b for b in owner.bindings if b.id != msg["binding_id"]]
    if len(owner.bindings) != before:
        await store.save(label="Bindung gelöscht")
        _engine(hass).rebuild()
    connection.send_result(msg["id"], {"ok": len(owner.bindings) != before})


@websocket_api.websocket_command({vol.Required("type"): "lichtregie/templates"})
@callback
def ws_templates(hass, connection, msg) -> None:
    connection.send_result(
        msg["id"],
        {
            "vorlagen": [
                {"key": key, "name": t["name"], "beschreibung": t["beschreibung"]}
                for key, t in TEMPLATES.items()
            ]
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/template/apply",
        vol.Required("control_id"): str,
        vol.Required("template"): str,
        vol.Optional("buttons"): [str],
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_template_apply(hass, connection, msg) -> None:
    """Belegt einen Taster nach einer Vorlage."""
    store = _store(hass)
    control = store.installation.control(msg["control_id"])
    if control is None:
        connection.send_error(msg["id"], "unbekannt", "Bedienelement nicht gefunden")
        return

    zone = store.installation.zone(control.zone_id or "")
    if zone is None:
        connection.send_error(
            msg["id"], "ohne_zone", "Dem Bedienelement ist keine Zone zugeordnet"
        )
        return

    buttons = msg.get("buttons") or [
        f"button_{i}" for i in range(1, max(2, control.buttons) + 1)
    ]
    scenes = [s.id for s in zone.scenes]
    bindings = apply_template(msg["template"], buttons, scenes)
    if not bindings:
        connection.send_error(msg["id"], "leer", "Vorlage ergibt keine Belegung")
        return

    control.bindings = bindings
    await store.save(label=f"Vorlage {msg['template']} für {control.name}")
    _engine(hass).rebuild()
    connection.send_result(
        msg["id"],
        {
            "ok": True,
            "bindungen": [
                {**b.to_dict(), "text": describe(b, zone)} for b in bindings
            ],
        },
    )


# --------------------------------------------------------------------------
# Tagesverlauf und Kalibrierung
# --------------------------------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/curves",
        vol.Optional("zone_id"): str,
    }
)
@callback
def ws_curves(hass, connection, msg) -> None:
    """Kurven und ihr Verlauf für den Editor."""
    engine = _engine(hass)
    sunrise, sunset = engine.sun_times()
    zone = _store(hass).installation.zone(msg.get("zone_id", ""))
    active = (
        (zone.curve_key or KIND_TO_CURVE.get(zone.kind, "wohnen")) if zone else "wohnen"
    )
    connection.send_result(
        msg["id"],
        {
            "aktiv": active,
            "aufgang": sunrise.isoformat(),
            "untergang": sunset.isoformat(),
            "kurven": [
                {
                    **curve.to_dict(),
                    "verlauf": curve.sample(sunrise.date(), sunrise, sunset, steps=48),
                }
                for curve in DEFAULT_CURVES.values()
            ],
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/calibrate",
        vol.Required("zone_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_calibrate(hass, connection, msg) -> None:
    """Startet die Kalibrierfahrt einer Zone."""
    result = await _engine(hass).calibrate(msg["zone_id"])
    if result.get("ok"):
        await _store(hass).save(label=f"Kalibrierung {msg['zone_id']}")
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/zone/settings",
        vol.Required("zone_id"): str,
        vol.Optional("daylight"): bool,
        vol.Optional("constant_light"): bool,
        vol.Optional("curve_key"): str,
        vol.Optional("setpoint_lux"): vol.Coerce(float),
        vol.Optional("linger"): vol.Coerce(float),
        vol.Optional("kind"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_zone_settings(hass, connection, msg) -> None:
    """Einzelne Werte einer Zone ändern, ohne sie komplett zu ersetzen."""
    store = _store(hass)
    zone = store.installation.zone(msg["zone_id"])
    if zone is None:
        connection.send_error(msg["id"], "unbekannt", "Zone nicht gefunden")
        return

    for field in ("daylight", "constant_light", "curve_key", "setpoint_lux", "linger", "kind"):
        if field in msg:
            setattr(zone, field, msg[field])

    await store.save(label=f"Einstellungen {zone.name}")
    _engine(hass).rebuild()
    connection.send_result(msg["id"], {"ok": True, "zone": zone.to_dict()})


# --------------------------------------------------------------------------
# Szenen bearbeiten
# --------------------------------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/scene/set",
        vol.Required("zone_id"): str,
        vol.Required("scene"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_scene_set(hass, connection, msg) -> None:
    """Legt eine Szene an oder ersetzt sie."""
    store = _store(hass)
    zone = store.installation.zone(msg["zone_id"])
    if zone is None:
        connection.send_error(msg["id"], "unbekannt", "Zone nicht gefunden")
        return

    data = dict(msg["scene"])
    if not data.get("id"):
        data["id"] = zone.new_scene_id()
    scene = Scene.from_dict(data)

    for index, existing in enumerate(zone.scenes):
        if existing.id == scene.id:
            zone.scenes[index] = scene
            break
    else:
        zone.scenes.append(scene)

    await store.save(label=f"Szene {scene.name} in {zone.name}")
    _engine(hass).rebuild()
    connection.send_result(msg["id"], {"ok": True, "scene": scene.to_dict()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/scene/delete",
        vol.Required("zone_id"): str,
        vol.Required("scene_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_scene_delete(hass, connection, msg) -> None:
    """Löscht eine Szene und alle Bindungen, die auf sie zeigen."""
    store = _store(hass)
    zone = store.installation.zone(msg["zone_id"])
    if zone is None:
        connection.send_error(msg["id"], "unbekannt", "Zone nicht gefunden")
        return

    before = len(zone.scenes)
    zone.scenes = [s for s in zone.scenes if s.id != msg["scene_id"]]
    if len(zone.scenes) == before:
        connection.send_result(msg["id"], {"ok": False})
        return

    # Verwaiste Bindungen mitnehmen — sonst zeigt eine Taste ins Leere.
    orphaned = 0
    for owner in [zone, *store.installation.controls]:
        keep = [
            b
            for b in owner.bindings
            if not (b.action == "scene" and b.scene_id == msg["scene_id"])
        ]
        orphaned += len(owner.bindings) - len(keep)
        owner.bindings = keep

    await store.save(label=f"Szene gelöscht in {zone.name}")
    _engine(hass).rebuild()
    connection.send_result(msg["id"], {"ok": True, "bindungen_entfernt": orphaned})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lichtregie/scene/snapshot",
        vol.Required("zone_id"): str,
    }
)
@websocket_api.require_admin
@callback
def ws_scene_snapshot(hass, connection, msg) -> None:
    """Liest den Ist-Zustand der Zone als Sollwerte zurück."""
    engine = _engine(hass)
    connection.send_result(
        msg["id"],
        {
            "levels": engine.snapshot_levels(msg["zone_id"]),
            "kelvin": engine.snapshot_kelvin(msg["zone_id"]),
        },
    )
