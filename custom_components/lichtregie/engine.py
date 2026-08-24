"""Der Taktgeber.

Hält je Zone einen Laufzeitzustand: Prioritätsstapel, Zustandsautomat,
Belegung, Timer. Läuft in eigenem Takt und hängt nicht daran, dass Home
Assistant gerade eine Automation abarbeitet.

Schneller Takt (250 ms): abgelaufene Ebenen, fällige Gesten, Verifikation.
Langsamer Takt (10 s): Helligkeitsnachführung.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    FADE_TRACKING,
    GESTURE_HOLD,
    GESTURE_RELEASE,
    HOLD_UNTIL_EMPTY,
    HOLD_UNTIL_PRESS,
    HOLD_WHILE_OCCUPIED,
    LAYER_BASE,
    LAYER_DAYLIGHT,
    LAYER_MANUAL,
    LAYER_PRESENCE,
    LAYER_SCENE,
    STATE_ARRIVAL,
    STATE_EMPTY,
    STATE_EXTENDED,
    STATE_FADING,
    STATE_LOCKED,
    STATE_NIGHT,
    STATE_OCCUPIED,
    TICK_CONTROL,
    TICK_FAST,
)
from .core.bindings import Context, conditions_hold, expiry_for
from .core.control import (
    Calibration,
    ConstantLight,
    calibration_from_run,
    own_lux,
)
from .core.daylight import DEFAULT_CURVES, KIND_TO_CURVE, DaylightCurve
from .core.journal import Journal
from .core.model import Binding, Installation, Zone
from .core.photometry import brightness_to_level, clamp
from .core.scenes import Command, dim_factor, resolve_scene
from .core.stack import Claim, PriorityStack
from .link.driver import Driver
from .link.gestures import ButtonEvent, GestureRecognizer, describe_source

_LOGGER = logging.getLogger(__name__)

MANUAL_HOLD = 7200.0  # zwei Stunden, dann fällt der Handbetrieb zurück
BLOCK_AFTER_MANUAL_OFF = 300.0  # Sperrzeit nach bewusstem Ausschalten
DIM_STEP_INTERVAL = 0.35
DIM_STEP = 0.06
ARRIVAL_SECONDS = 5.0  # danach gilt die Ankunft als normale Belegung
SETTLE = 4.0  # Beruhigungszeit des Lux-Sensors bei der Kalibrierfahrt


@dataclass
class ZoneRuntime:
    """Laufzeitzustand einer Zone."""

    zone: Zone
    stack: PriorityStack = field(default_factory=PriorityStack)
    state: str = STATE_EMPTY
    occupied_since: float | None = None
    last_motion: float | None = None
    blocked_until: float = 0.0
    warned: bool = False
    last_lux: float | None = None
    dimming: tuple[str, int] | None = None  # (Richtung, Zeitmarke)
    last_dim_step: float = 0.0
    regulator: ConstantLight | None = None
    calibration: Calibration | None = None
    control_factor: float = 1.0
    last_control: float = 0.0
    last_daylight: tuple[int, float] | None = None
    calibrating: bool = False
    previous_scene: str | None = None
    dim_direction: int = 1

    def occupied(self, now: float) -> bool:
        if self.last_motion is None:
            return False
        return (now - self.last_motion) <= self.zone.linger


class Engine:
    """Führt die Anlage."""

    def __init__(
        self,
        hass: HomeAssistant,
        installation: Installation,
        journal: Journal | None = None,
        runtime_store=None,
    ) -> None:
        self.hass = hass
        self.installation = installation
        self.runtime_store = runtime_store
        self.journal = journal or Journal()
        self.driver = Driver(hass, self.journal)
        self.zones: dict[str, ZoneRuntime] = {}
        self.recognizers: dict[str, GestureRecognizer] = {}
        self._unsubs: list[Callable[[], None]] = []
        self._listeners: list[Callable[[str, dict], None]] = []
        self._fired: set[str] = set()
        self._running = False

    # -- Leben --------------------------------------------------------------

    async def async_start(self) -> None:
        self.rebuild()
        self._running = True
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._tick, dt_util.dt.timedelta(seconds=TICK_FAST)
            )
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._slow_tick, dt_util.dt.timedelta(seconds=TICK_CONTROL)
            )
        )
        self._subscribe()
        await self._restore_runtime()
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._persist, dt_util.dt.timedelta(seconds=60)
            )
        )
        self.journal.log("", "start", "Lichtregie gestartet", f"{len(self.zones)} Zonen")

    async def async_stop(self) -> None:
        await self._persist()
        self._running = False
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    async def _restore_runtime(self) -> None:
        """Holt den Zustand nach einem Neustart zurück.

        Ist die Sicherung älter als eine Stunde, wird sie verworfen — was
        gestern Abend galt, gilt heute Morgen nicht mehr.
        """
        if self.runtime_store is None:
            return
        await self.runtime_store.load()
        if self.runtime_store.age() > 3600:
            return

        now = time.monotonic()
        restored = 0
        for zone_id, data in self.runtime_store.zones().items():
            runtime = self.zones.get(zone_id)
            if runtime is None:
                continue
            runtime.stack.restore(data.get("stack", []), now)
            runtime.state = data.get("state", STATE_EMPTY)
            runtime.previous_scene = data.get("previous_scene")
            if data.get("blocked_for"):
                runtime.blocked_until = now + float(data["blocked_for"])
            if data.get("occupied_for"):
                runtime.occupied_since = now - float(data["occupied_for"])
            restored += 1

        if restored:
            self.journal.log(
                "",
                "start",
                "Zustand wiederhergestellt",
                f"{restored} Zonen aus der Sicherung von vor "
                f"{self.runtime_store.age() / 60:.0f} min",
            )

    async def _persist(self, _now=None) -> None:
        """Sichert den Laufzeitzustand."""
        if self.runtime_store is None:
            return
        now = time.monotonic()
        payload = {}
        for zone_id, runtime in self.zones.items():
            payload[zone_id] = {
                "stack": runtime.stack.store(now),
                "state": runtime.state,
                "previous_scene": runtime.previous_scene,
                "blocked_for": max(0.0, runtime.blocked_until - now),
                "occupied_for": (
                    now - runtime.occupied_since if runtime.occupied_since else 0.0
                ),
            }
        try:
            await self.runtime_store.save(payload)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Laufzeitzustand nicht gesichert: %s", err)

    def rebuild(self) -> None:
        """Übernimmt eine geänderte Konfiguration ohne Neustart."""
        keep = self.zones
        self.zones = {}
        for zone in self.installation.zones:
            if not zone.enabled:
                continue
            previous = keep.get(zone.id)
            runtime = ZoneRuntime(zone=zone)
            if previous is not None:
                runtime.stack = previous.stack
                runtime.state = previous.state
                runtime.last_motion = previous.last_motion
                runtime.last_lux = previous.last_lux
                runtime.control_factor = previous.control_factor
            runtime.calibration = Calibration.from_dict(zone.calibration or {})
            runtime.regulator = ConstantLight(
                setpoint=zone.setpoint_lux, floor=0.05, ceiling=1.0
            )
            self.zones[zone.id] = runtime
        for control in self.installation.controls:
            self.recognizers.setdefault(control.id, GestureRecognizer())
        self._resubscribe()

    # -- Abonnements --------------------------------------------------------

    def _resubscribe(self) -> None:
        for unsub in list(self._unsubs[3:]):
            unsub()
        del self._unsubs[3:]
        if self._running:
            self._subscribe()

    def _subscribe(self) -> None:
        watched: list[str] = []
        for runtime in self.zones.values():
            watched.extend(runtime.zone.presence_entities)
            watched.extend(runtime.zone.door_entities)
            watched.extend(runtime.zone.entity_ids)
            if runtime.zone.lux_entity:
                watched.append(runtime.zone.lux_entity)

        for control in self.installation.controls:
            if control.entity_id:
                watched.append(control.entity_id)

        if watched:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, list(set(watched)), self._on_state
                )
            )

        # Rohereignisse der Bussysteme — für Wandsender ohne Entität.
        for event_type in ("deconz_event", "zha_event", "xiaomi_aqara.click"):
            self._unsubs.append(
                self.hass.bus.async_listen(event_type, self._on_bus_event)
            )

    # -- Ereignisse ---------------------------------------------------------

    @callback
    def _on_state(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        if new is None:
            return
        now = time.monotonic()

        # Bedienelemente mit Entität
        for control in self.installation.controls:
            if control.entity_id != entity_id:
                continue
            recognizer = self.recognizers.setdefault(control.id, GestureRecognizer())
            if control.source == "event_entity":
                kind = new.attributes.get("event_type")
                if kind:
                    for gesture in recognizer.feed(control.id, "1", str(kind), now):
                        self._on_gesture(control, gesture)
            else:
                for gesture in recognizer.feed_binary(
                    control.id, "1", new.state == "on", now
                ):
                    self._on_gesture(control, gesture)
            return

        for runtime in self.zones.values():
            zone = runtime.zone
            if entity_id in zone.presence_entities:
                if new.state == "on":
                    self._on_motion(runtime, entity_id, now)
                else:
                    runtime.last_motion = now
            elif entity_id in zone.door_entities and new.state == "on":
                self._on_motion(runtime, entity_id, now, source="Tür")
            elif entity_id == zone.lux_entity:
                try:
                    runtime.last_lux = float(new.state)
                except (TypeError, ValueError):
                    runtime.last_lux = None
            elif entity_id in zone.entity_ids:
                self._check_foreign(runtime, entity_id, new, old, now)

    @callback
    def _on_bus_event(self, event: Event) -> None:
        """Rohereignis eines Bussystems einem Bedienelement zuordnen."""
        data = dict(event.data)
        device_id = data.get("device_id")
        now = time.monotonic()
        for control in self.installation.controls:
            if control.device_id and control.device_id == device_id:
                recognizer = self.recognizers.setdefault(
                    control.id, GestureRecognizer()
                )
                button, action = describe_source(data)
                for gesture in recognizer.feed(control.id, button, action, now):
                    self._on_gesture(control, gesture)
                return

    # -- Bewegung -----------------------------------------------------------

    def _on_motion(
        self, runtime: ZoneRuntime, entity_id: str, now: float, source: str = "Bewegung"
    ) -> None:
        zone = runtime.zone
        runtime.last_motion = now
        runtime.warned = False

        # Ankunft: der Raum war leer und ist es nicht mehr.
        if runtime.occupied_since is None:
            runtime.occupied_since = now
            if runtime.state in (STATE_EMPTY, STATE_FADING):
                runtime.state = STATE_ARRIVAL

        if now < runtime.blocked_until:
            return

        if runtime.stack.has(LAYER_PRESENCE):
            runtime.stack.extend(LAYER_PRESENCE, zone.linger, now)
            if runtime.state in (STATE_FADING, STATE_ARRIVAL):
                runtime.state = STATE_OCCUPIED
                self.hass.async_create_task(self._apply(runtime, "Bewegung erneut"))
            return

        # Höhere Ebene aktiv? Dann nur den Nachlauf pflegen.
        active = runtime.stack.active
        if active is not None and active.layer > LAYER_PRESENCE:
            return

        for binding, why in self._bindings_for(runtime, {"art": "bewegung"}, now):
            self.hass.async_create_task(
                self._run_binding(
                    runtime, binding, f"{source} {entity_id}", now, why
                )
            )
            return

    # -- Bedienung ----------------------------------------------------------

    def _on_gesture(self, control, event: ButtonEvent) -> None:
        zone_id = control.zone_id
        runtime = self.zones.get(zone_id) if zone_id else None
        now = event.at

        self.journal.log(
            zone_id or "",
            "bedienung",
            f"{control.name}: Taste {event.button}, {event.gesture}",
            f"Rohereignis {event.raw}",
            control=control.id,
        )
        self._notify("gesture", {
            "control": control.id,
            "button": event.button,
            "gesture": event.gesture,
            "raw": event.raw,
        })

        if runtime is None:
            return

        if event.gesture == GESTURE_HOLD:
            # Richtung wechselt bei jedem neuen Halten — so kennt man es von
            # Wippen, die nur ein Ereignis je Seite liefern.
            levels, _, _ = runtime.stack.resolve()
            current = max(levels.values()) if levels else 0.0
            if current <= 0.02:
                runtime.dim_direction = 1
            elif current >= 0.99:
                runtime.dim_direction = -1
            else:
                runtime.dim_direction = -runtime.dim_direction
            runtime.dimming = (event.button, runtime.dim_direction)
            runtime.last_dim_step = now
            return
        if event.gesture == GESTURE_RELEASE:
            runtime.dimming = None
            return

        context = self._context(runtime, now)
        skipped: list[str] = []
        for binding in control.bindings:
            if not binding.enabled:
                continue
            if binding.trigger.get("taste") != event.button:
                continue
            if binding.trigger.get("geste") != event.gesture:
                continue
            ok, why = conditions_hold(binding, context)
            if not ok:
                skipped.append(why)
                continue
            self.hass.async_create_task(
                self._run_binding(
                    runtime, binding, f"{control.name} Taste {event.button}", now, why
                )
            )
            return

        if skipped:
            self.journal.log(
                runtime.zone.id,
                "uebersprungen",
                f"Taste {event.button} ohne Wirkung",
                " · ".join(skipped),
            )
        else:
            _LOGGER.debug(
                "Keine Bindung für Taste %s, Geste %s", event.button, event.gesture
            )

    # -- Bindungen ----------------------------------------------------------

    def _context(self, runtime: ZoneRuntime, now: float) -> Context:
        """Alles, was zur Prüfung einer Bedingung gebraucht wird."""
        local = dt_util.now()
        return Context(
            now=now,
            lux=runtime.last_lux,
            state=runtime.state,
            mode=self.installation.mode,
            night=self._is_night(runtime.zone),
            occupied=runtime.occupied(now),
            weekday=local.weekday(),
            minute_of_day=local.hour * 60 + local.minute,
        )

    def _bindings_for(
        self, runtime: ZoneRuntime, trigger: dict, now: float
    ) -> list[tuple[Binding, str]]:
        context = self._context(runtime, now)
        out = []
        for binding in runtime.zone.bindings:
            if not binding.enabled:
                continue
            if binding.trigger.get("art") != trigger.get("art"):
                continue
            ok, why = conditions_hold(binding, context)
            if not ok:
                continue
            out.append((binding, why))
        return out

    async def _run_binding(
        self,
        runtime: ZoneRuntime,
        binding: Binding,
        source: str,
        now: float,
        why: str = "",
    ) -> None:
        zone = runtime.zone

        if binding.action == "zone_aus":
            await self.turn_off(zone.id, source=source)
            return
        if binding.action == "etage_aus":
            for other in list(self.zones):
                await self.turn_off(other, source=f"{source} (Etage)")
            return
        if binding.action == "automatik":
            runtime.stack.release_above(LAYER_BASE)
            runtime.blocked_until = 0.0
            await self._apply(runtime, f"{source}: Automatik")
            return
        if binding.action == "weiter":
            await self.next_scene(zone.id, source=source)
            return

        scene = zone.scene(binding.scene_id or "")
        if scene is None:
            _LOGGER.warning("Bindung %s zeigt auf unbekannte Szene", binding.id)
            return

        # Haltemodell „bis Gegendruck": derselbe Auslöser schaltet wieder aus.
        running = runtime.stack.get(binding.layer)
        if (
            binding.hold == HOLD_UNTIL_PRESS
            and running is not None
            and running.scene_id == scene.id
        ):
            runtime.stack.release(binding.layer)
            self.journal.log(
                zone.id,
                "ablauf",
                f"Szene „{scene.name}“ beendet",
                f"{source} · zweiter Druck",
                layer=binding.layer,
                scene_id=scene.id,
            )
            await self._after(runtime, running, now)
            return

        if scene.max_lux is not None and runtime.last_lux is not None:
            if runtime.last_lux > scene.max_lux:
                self.journal.log(
                    zone.id,
                    "uebersprungen",
                    f"Szene „{scene.name}“ nicht aufgerufen",
                    f"Fremdlicht {runtime.last_lux:.0f} lx über Grenze {scene.max_lux:.0f} lx",
                    lux=runtime.last_lux,
                )
                return

        expires = expiry_for(binding, zone, self._context(runtime, now))
        levels = scene.resolve(zone)
        kelvin = (
            {cid: scene.kelvin for cid in levels} if scene.kelvin else {}
        )

        if running is not None and running.scene_id and running.scene_id != scene.id:
            runtime.previous_scene = running.scene_id

        # Weitere Zonen mitschalten, wenn die Bindung sie nennt.
        for other_id in binding.zones or []:
            other = self.zones.get(other_id)
            if other is None or other is runtime:
                continue
            twin = other.zone.scene(scene.id)
            if twin is None:
                continue
            other.stack.push(
                Claim(
                    layer=binding.layer,
                    scene_id=twin.id,
                    levels=twin.resolve(other.zone),
                    kelvin=(
                        {c.id: twin.kelvin for c in other.zone.circuits}
                        if twin.kelvin
                        else {}
                    ),
                    fade=twin.fade,
                    source=f"{source} (mit {zone.name})",
                    expires_at=expires,
                    hold=binding.hold,
                    then=binding.then,
                ),
                now,
            )
            await self._apply(other, f"{source} → {twin.name}", scene_id=twin.id)

        runtime.stack.push(
            Claim(
                layer=binding.layer,
                scene_id=scene.id,
                levels=levels,
                kelvin=kelvin,
                fade=scene.fade,
                source=source,
                expires_at=expires,
                hold=binding.hold,
                then=binding.then,
            ),
            now,
        )
        if runtime.state in (STATE_EMPTY, STATE_FADING):
            runtime.state = STATE_ARRIVAL
        await self._apply(
            runtime,
            f"{source} → {scene.name}" + (f" ({why})" if why else ""),
            scene_id=scene.id,
        )

    # -- Fremdeingriffe -----------------------------------------------------

    def _check_foreign(
        self, runtime: ZoneRuntime, entity_id: str, new, old, now: float
    ) -> None:
        """Erkennt, wenn jemand an der Engine vorbei geschaltet hat."""
        if self.driver.was_ours(entity_id, now):
            return
        if old is None or new.state == old.state and new.attributes.get(
            "brightness"
        ) == (old.attributes.get("brightness") if old else None):
            return

        zone = runtime.zone
        circuit = next(
            (c for c in zone.circuits if entity_id in c.entity_ids), None
        )
        if circuit is None:
            return
        fixture = next(f for f in circuit.fixtures if f.entity_id == entity_id)

        if new.state == "off":
            # Bewusstes Ausschalten: Sperrzeit, damit nicht sofort wieder angeht.
            runtime.stack.release_above(LAYER_BASE)
            runtime.blocked_until = now + BLOCK_AFTER_MANUAL_OFF
            self.journal.log(
                zone.id,
                "abweichung",
                "Von Hand ausgeschaltet",
                f"{entity_id} · Sperrzeit {BLOCK_AFTER_MANUAL_OFF/60:.0f} min",
                layer=LAYER_MANUAL,
            )
            self._notify("zone", self.zone_state(zone.id))
            return

        brightness = new.attributes.get("brightness")
        level = (
            brightness_to_level(
                int(brightness), fixture.curve, fixture.min_flux, fixture.max_flux
            )
            if brightness
            else 1.0
        )

        claim = runtime.stack.get(LAYER_MANUAL) or Claim(
            layer=LAYER_MANUAL, source="Fremdeingriff"
        )
        claim.levels[circuit.id] = level
        claim.expires_at = now + MANUAL_HOLD
        claim.hold = "2 h"
        runtime.stack.push(claim, now)

        self.journal.log(
            zone.id,
            "abweichung",
            "Abweichung erkannt",
            f"{entity_id} steht auf {level*100:.0f} % ohne eigenen Stellbefehl · "
            f"übernommen auf Ebene {LAYER_MANUAL}",
            layer=LAYER_MANUAL,
        )
        self._notify("zone", self.zone_state(zone.id))

    # -- Takt ---------------------------------------------------------------

    async def _tick(self, _now=None) -> None:
        now = time.monotonic()

        for control in self.installation.controls:
            recognizer = self.recognizers.get(control.id)
            if recognizer is None or not recognizer.waiting:
                continue
            for gesture in recognizer.due(control.id, now):
                self._on_gesture(control, gesture)

        for runtime in self.zones.values():
            await self._tick_zone(runtime, now)

        await self.driver.verify()

    async def _tick_zone(self, runtime: ZoneRuntime, now: float) -> None:
        zone = runtime.zone

        if runtime.dimming is not None and now - runtime.last_dim_step >= DIM_STEP_INTERVAL:
            runtime.last_dim_step = now
            await self._dim_step(runtime, now)

        expired = runtime.stack.expire(now)
        if expired:
            for claim in expired:
                self.journal.log(
                    zone.id,
                    "ablauf",
                    f"Ebene {claim.layer} abgelaufen",
                    f"Auslöser war {claim.source} · danach {claim.then}",
                    layer=claim.layer,
                )
            await self._after(runtime, expired[0], now)
            self._notify("zone", self.zone_state(zone.id))
            return

        # Vorwarnung und Zustandswechsel
        claim = runtime.stack.get(LAYER_PRESENCE)
        if claim is not None and claim.expires_at is not None:
            remaining = claim.expires_at - now
            if 0 < remaining <= zone.warn_before and not runtime.warned:
                runtime.warned = True
                runtime.state = STATE_FADING
                self.journal.log(
                    zone.id,
                    "vorwarnung",
                    "Vorwarnung vor dem Ausschalten",
                    f"auf {zone.warn_level*100:.0f} % gedimmt, {zone.warn_before:.0f} s Rest",
                )
                await self._apply(runtime, "Vorwarnung", factor=zone.warn_level)

        # Zustandsautomat: Ankunft läuft nach kurzer Zeit in Belegt über,
        # Belegt nach der Vertiefungsschwelle in Vertieft, und wenn niemand
        # mehr da ist, fällt alles auf Leer zurück.
        if runtime.occupied_since is not None:
            age = now - runtime.occupied_since
            if runtime.state == STATE_ARRIVAL and age >= ARRIVAL_SECONDS:
                runtime.state = STATE_OCCUPIED
            elif runtime.state == STATE_OCCUPIED and age >= zone.extended_after:
                runtime.state = STATE_EXTENDED
                self.journal.log(
                    zone.id,
                    "zustand",
                    "Zone gilt als vertieft belegt",
                    f"seit {age / 60:.0f} min ohne Unterbrechung",
                )

        if not runtime.occupied(now) and not runtime.stack.has(LAYER_PRESENCE):
            if runtime.state not in (STATE_EMPTY, STATE_LOCKED):
                runtime.state = STATE_EMPTY
                runtime.occupied_since = None
                await self._release_holds_on_empty(runtime, now)

        if self._is_night(zone) and runtime.state == STATE_EMPTY:
            runtime.state = STATE_NIGHT
        elif not self._is_night(zone) and runtime.state == STATE_NIGHT:
            runtime.state = STATE_EMPTY

    async def _release_holds_on_empty(self, runtime: ZoneRuntime, now: float) -> None:
        """Gibt Anmeldungen frei, deren Haltemodell an der Belegung hängt.

        ``bis Zone leer`` läuft nicht über eine Uhr ab, sondern genau hier.
        """
        released = []
        for layer in list(runtime.stack.layers):
            claim = runtime.stack.get(layer)
            if claim is None or layer <= LAYER_BASE:
                continue
            if claim.hold in (HOLD_UNTIL_EMPTY, HOLD_WHILE_OCCUPIED):
                runtime.stack.release(layer)
                released.append(claim)

        if not released:
            return

        for claim in released:
            self.journal.log(
                runtime.zone.id,
                "ablauf",
                f"Ebene {claim.layer} freigegeben",
                "Zone ist leer",
                layer=claim.layer,
            )
        await self._after(runtime, released[0], now)

    async def _after(self, runtime: ZoneRuntime, claim: Claim, now: float) -> None:
        """Führt aus, was nach dem Ende einer Anmeldung passieren soll.

        Das Feld ``Danach`` einer Bindung: zurück zur Automatik (die Ebene
        darunter übernimmt), die vorherige Szene, der Grundzustand oder aus.
        """
        what = claim.then or "automatik"

        if what == "aus":
            runtime.stack.release_above(LAYER_BASE)
            await self._apply(runtime, "Nach Ablauf: aus")
            return

        if what == "grundzustand":
            runtime.stack.release_above(LAYER_BASE)
            base = runtime.stack.get(LAYER_BASE)
            await self._apply(
                runtime, "Nach Ablauf: Grundzustand" if base else "Nach Ablauf: aus"
            )
            return

        if what == "vorherige" and runtime.previous_scene:
            scene = runtime.zone.scene(runtime.previous_scene)
            if scene is not None:
                runtime.stack.push(
                    Claim(
                        layer=claim.layer,
                        scene_id=scene.id,
                        levels=scene.resolve(runtime.zone),
                        kelvin=(
                            {c.id: scene.kelvin for c in runtime.zone.circuits}
                            if scene.kelvin
                            else {}
                        ),
                        fade=scene.fade,
                        source="vorherige Szene",
                        expires_at=None,
                        hold=HOLD_UNTIL_EMPTY,
                    ),
                    now,
                )
                await self._apply(
                    runtime, f"Nach Ablauf: zurück zu „{scene.name}“", scene_id=scene.id
                )
                return

        await self._apply(runtime, "Nach Ablauf: Automatik")

    async def _dim_step(self, runtime: ZoneRuntime, now: float) -> None:
        """Dimmt den Zonenmaster, solange eine Taste gehalten wird."""
        direction = runtime.dimming[1] if runtime.dimming else 0
        claim = runtime.stack.get(LAYER_MANUAL)
        if claim is None:
            levels, kelvin, fade = runtime.stack.resolve()
            claim = Claim(
                layer=LAYER_MANUAL,
                levels=dict(levels),
                kelvin=dict(kelvin),
                fade=0.3,
                source="Dimmen",
            )
        for circuit_id, level in list(claim.levels.items()):
            claim.levels[circuit_id] = clamp(level + DIM_STEP * direction)
        claim.expires_at = now + MANUAL_HOLD
        runtime.stack.push(claim, now)
        await self._apply(runtime, "Dimmen", fade=DIM_STEP_INTERVAL)

    # -- Langsamer Takt: Tagesverlauf und Konstantlicht ---------------------

    async def _slow_tick(self, _now=None) -> None:
        now = time.monotonic()
        await self._run_schedule(now)
        for runtime in self.zones.values():
            if runtime.calibrating:
                continue
            try:
                await self._track_daylight(runtime, now)
                await self._regulate(runtime, now)
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Regelung %s: %s", runtime.zone.id, err)

    async def _run_schedule(self, now: float) -> None:
        """Zeit- und sonnenstandsgebundene Bindungen auslösen.

        Ein Auslöser feuert genau einmal je Tag. Gerechnet wird in Minuten
        seit Mitternacht; der Vergleich läuft über das Fenster seit dem
        letzten Takt, damit kein Zeitpunkt verpasst wird.
        """
        local = dt_util.now()
        minute = local.hour * 60 + local.minute
        sunrise, sunset = self.sun_times()
        sun_minutes = {
            "aufgang": sunrise.hour * 60 + sunrise.minute,
            "untergang": sunset.hour * 60 + sunset.minute,
        }

        for runtime in self.zones.values():
            for binding in runtime.zone.bindings:
                if not binding.enabled or binding.trigger.get("art") != "zeit":
                    continue

                anchor = binding.trigger.get("anker", "uhr")
                offset = int(binding.trigger.get("versatz", 0))
                if anchor in sun_minutes:
                    target = (sun_minutes[anchor] + offset) % 1440
                else:
                    raw = str(binding.trigger.get("um", "00:00"))
                    hour, _, rest = raw.partition(":")
                    target = (int(hour) * 60 + int(rest or 0) + offset) % 1440

                if target != minute:
                    continue

                marker = f"{binding.id}:{local.date().isoformat()}"
                if marker in self._fired:
                    continue
                self._fired.add(marker)

                ok, why = conditions_hold(binding, self._context(runtime, now))
                if not ok:
                    self.journal.log(
                        runtime.zone.id,
                        "uebersprungen",
                        "Zeitauslöser übersprungen",
                        why,
                    )
                    continue

                await self._run_binding(
                    runtime, binding, f"Zeitplan {local:%H:%M}", now, why
                )

        # Marker des Vortags aufräumen, damit die Menge nicht wächst.
        if minute == 0:
            today = local.date().isoformat()
            self._fired = {m for m in self._fired if m.endswith(today)}

    def _curve_for(self, zone: Zone) -> DaylightCurve:
        key = zone.curve_key or KIND_TO_CURVE.get(zone.kind, "wohnen")
        return DEFAULT_CURVES.get(key, DEFAULT_CURVES["wohnen"])

    def sun_times(self):
        """Aufgang und Untergang aus der Sonnen-Entität, sonst Näherung."""
        local = dt_util.now()
        sun = self.hass.states.get("sun.sun")
        rising = setting = None
        if sun is not None:
            raw_rise = sun.attributes.get("next_rising")
            raw_set = sun.attributes.get("next_setting")
            rising = dt_util.parse_datetime(raw_rise) if raw_rise else None
            setting = dt_util.parse_datetime(raw_set) if raw_set else None

        def same_day(value, hour: int):
            if value is None:
                return local.replace(hour=hour, minute=0, second=0, microsecond=0)
            value = dt_util.as_local(value)
            return value.replace(year=local.year, month=local.month, day=local.day)

        return same_day(rising, 7), same_day(setting, 20)

    def daylight_now(self, zone: Zone) -> tuple[int, float]:
        """Farbtemperatur und Helligkeitsfaktor des Tagesverlaufs."""
        sunrise, sunset = self.sun_times()
        return self._curve_for(zone).at_time(dt_util.now(), sunrise, sunset)

    async def _track_daylight(self, runtime: ZoneRuntime, now: float) -> None:
        """Führt Ebene 20 nach — nur für Kreise, die niemand sonst bestimmt."""
        zone = runtime.zone
        if not zone.daylight:
            runtime.stack.release(LAYER_DAYLIGHT)
            return

        kelvin, factor = self.daylight_now(zone)
        if runtime.last_daylight == (kelvin, round(factor, 2)):
            return
        runtime.last_daylight = (kelvin, round(factor, 2))

        claim = runtime.stack.get(LAYER_DAYLIGHT) or Claim(
            layer=LAYER_DAYLIGHT, source="Tagesverlauf", fade=FADE_TRACKING
        )
        claim.kelvin = {c.id: kelvin for c in zone.circuits if c.color_temp}
        claim.source = f"Tagesverlauf {kelvin} K"
        runtime.stack.push(claim, now)

        # Nur nachführen, wenn gerade Licht an ist — sonst nichts anfassen.
        levels, _, _ = runtime.stack.resolve()
        if not any(v > 0 for v in levels.values()):
            return
        await self._apply(runtime, f"Tagesverlauf {kelvin} K", fade=FADE_TRACKING)

    async def _regulate(self, runtime: ZoneRuntime, now: float) -> None:
        """Konstantlichtregelung — nur mit gültiger Kalibrierung."""
        zone = runtime.zone
        if not zone.constant_light or runtime.regulator is None:
            return
        if runtime.calibration is None or not runtime.calibration.valid:
            return
        if runtime.last_lux is None:
            return

        levels, _, _ = runtime.stack.resolve()
        if not any(v > 0 for v in levels.values()):
            return

        active = runtime.stack.active
        if active is not None and active.layer >= LAYER_MANUAL:
            return  # Handbetrieb wird nicht nachgeregelt

        curves = {}
        for circuit in zone.circuits:
            if circuit.fixtures:
                fixture = circuit.fixtures[0]
                curves[circuit.id] = (
                    fixture.curve,
                    fixture.min_flux,
                    fixture.max_flux,
                )

        own = own_lux(runtime.calibration, levels, curves)
        dt = max(1.0, now - (runtime.last_control or now - TICK_CONTROL))
        runtime.last_control = now

        target, why = runtime.regulator.step(
            measured=runtime.last_lux,
            own=own,
            current=runtime.control_factor,
            dt=dt,
            now=now,
        )
        if target is None:
            return

        runtime.control_factor = target
        runtime.regulator.disturb(now)
        self.journal.log(
            zone.id,
            "regelung",
            "Konstantlicht nachgeführt",
            why,
            lux=runtime.last_lux,
        )
        await self._apply(
            runtime, "Konstantlichtregelung", factor=target, fade=FADE_TRACKING
        )

    # -- Kalibrierfahrt -----------------------------------------------------

    async def calibrate(self, zone_id: str) -> dict[str, Any]:
        """Misst den Lux-Beitrag jedes Lichtkreises am Sensor der Zone.

        Fährt jeden Kreis einzeln auf vollen Sollwert und misst den Zuwachs.
        Läuft nur, wenn der Raum leer ist und es dunkel genug ist — sonst
        misst man das Tageslicht mit.
        """
        runtime = self.zones.get(zone_id)
        if runtime is None:
            return {"ok": False, "grund": "Zone unbekannt"}
        zone = runtime.zone
        if not zone.lux_entity:
            return {"ok": False, "grund": "Kein Helligkeitssensor zugeordnet"}
        if runtime.occupied(time.monotonic()):
            return {"ok": False, "grund": "Raum ist belegt"}

        runtime.calibrating = True
        saved = runtime.stack.snapshot(time.monotonic())
        self.journal.log(zone.id, "kalibrierung", "Kalibrierfahrt gestartet")

        async def read_lux() -> float | None:
            await asyncio.sleep(SETTLE)
            state = self.hass.states.get(zone.lux_entity)
            try:
                return float(state.state)
            except (AttributeError, TypeError, ValueError):
                return None

        try:
            # Alles aus, Dunkelwert messen.
            await self.driver.apply(
                resolve_scene(zone, {}, fade=1.0, reason="Kalibrierung"), zone.id
            )
            dark = await read_lux()
            if dark is None:
                return {"ok": False, "grund": "Sensor liefert keinen Messwert"}
            if dark > zone.setpoint_lux:
                return {
                    "ok": False,
                    "grund": f"Zu hell für die Messung ({dark:.0f} lx) — nachts wiederholen",
                }

            readings: dict[str, float] = {}
            for circuit in zone.circuits:
                if not circuit.enabled:
                    continue
                await self.driver.apply(
                    resolve_scene(
                        zone, {circuit.id: 1.0}, fade=0.5, reason="Kalibrierung"
                    ),
                    zone.id,
                )
                value = await read_lux()
                if value is not None:
                    readings[circuit.id] = value
                self.journal.log(
                    zone.id,
                    "kalibrierung",
                    f"Kreis {circuit.name} gemessen",
                    f"{value:.0f} lx bei vollem Sollwert" if value else "kein Messwert",
                )

            calibration = calibration_from_run(dark, readings, at=time.time())
            zone.calibration = calibration.to_dict()
            runtime.calibration = calibration

            await self.driver.apply(
                resolve_scene(zone, {}, fade=1.0, reason="Kalibrierung beendet"),
                zone.id,
            )
            self.journal.log(
                zone.id,
                "kalibrierung",
                "Kalibrierfahrt beendet",
                f"Dunkelwert {dark:.0f} lx · "
                + " · ".join(
                    f"{zone.circuit(k).name if zone.circuit(k) else k} {v:.0f} lx"
                    for k, v in calibration.contributions.items()
                ),
            )
            return {"ok": calibration.valid, "kalibrierung": calibration.to_dict()}
        finally:
            runtime.calibrating = False
            del saved
            await self._apply(runtime, "Nach der Kalibrierfahrt")

    # -- Ausgabe ------------------------------------------------------------

    async def _apply(
        self,
        runtime: ZoneRuntime,
        reason: str,
        *,
        factor: float | None = None,
        fade: float | None = None,
        scene_id: str | None = None,
    ) -> None:
        zone = runtime.zone
        levels, kelvin, scene_fade = runtime.stack.resolve()

        if factor is None:
            if zone.constant_light and runtime.calibration and runtime.calibration.valid:
                factor = runtime.control_factor
            else:
                factor = dim_factor(
                    runtime.last_lux, zone.lux_on_below * 0.15, zone.lux_off_above
                )

        daylight_kelvin = None
        if zone.daylight:
            daylight_kelvin = (runtime.last_daylight or self.daylight_now(zone))[0]

        commands: list[Command] = resolve_scene(
            zone,
            levels,
            kelvin,
            dim_factor=factor,
            fade=fade if fade is not None else scene_fade,
            night=self._is_night(zone),
            daylight_kelvin=daylight_kelvin,
            reason=reason,
        )
        sent = await self.driver.apply(commands, zone.id)
        if sent and runtime.regulator is not None:
            runtime.regulator.disturb(time.monotonic())

        self.journal.log(
            zone.id,
            "ausgabe",
            reason,
            f"{sent} Aufruf(e) · Faktor {factor:.2f}"
            + (f" · {runtime.last_lux:.0f} lx" if runtime.last_lux is not None else ""),
            layer=runtime.stack.active.layer if runtime.stack.active else None,
            scene_id=scene_id,
            lux=runtime.last_lux,
        )
        self._notify("zone", self.zone_state(zone.id))

    def _is_night(self, zone: Zone) -> bool:
        """Liegt der aktuelle Zeitpunkt im Nachtfenster der Zone?

        Anfang ist immer eine Uhrzeit. Das Ende ist entweder ebenfalls eine
        Uhrzeit oder ``sunrise`` — dann endet die Nacht mit dem Sonnenaufgang,
        verschiebt sich also über das Jahr.
        """
        now = dt_util.now()
        minute = now.hour * 60 + now.minute

        def to_minutes(value: str) -> int | None:
            try:
                hour, _, rest = value.partition(":")
                return int(hour) * 60 + int(rest or 0)
            except ValueError:
                return None

        start = to_minutes(zone.night_start)
        if start is None:
            return False

        if (zone.night_end or "sunrise").strip().lower() in ("sunrise", "aufgang"):
            sunrise, _ = self.sun_times()
            end = sunrise.hour * 60 + sunrise.minute
        else:
            end = to_minutes(zone.night_end)
            if end is None:
                return False

        if start <= end:
            return start <= minute < end
        return minute >= start or minute < end

    # -- Öffentliche Befehle -----------------------------------------------

    async def apply_scene(
        self, zone_id: str, scene_id: str, source: str = "Panel"
    ) -> bool:
        runtime = self.zones.get(zone_id)
        if runtime is None:
            return False
        scene = runtime.zone.scene(scene_id)
        if scene is None:
            return False
        binding = Binding(
            id="direkt",
            scene_id=scene_id,
            layer=LAYER_SCENE,
            hold=HOLD_UNTIL_EMPTY,
        )
        await self._run_binding(runtime, binding, source, time.monotonic())
        return True

    async def preview_fixture(
        self,
        zone_id: str,
        entity_id: str,
        level: float,
        curve: str,
        min_flux: float,
        max_flux: float,
    ) -> int:
        """Fährt eine einzelne Leuchte auf einen Sollwert.

        Für die Kontrolle beim Einstellen der Betriebsgrenzen: der Wert 1.0
        zeigt, was volle Szenenhelligkeit später bedeutet, der Wert 0.0 den
        kleinsten Punkt, an dem die Leuchte noch brennen soll. Gerechnet
        wird mit den übergebenen Grenzen, nicht mit den gespeicherten —
        sonst sähe man die Änderung erst nach dem Speichern.
        """
        from .core.photometry import level_to_brightness

        brightness = level_to_brightness(max(level, 0.0001), curve, min_flux, max_flux)
        await self.hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": entity_id, "brightness": brightness, "transition": 0.3},
            blocking=False,
        )
        self.journal.log(
            zone_id,
            "vorschau",
            "Grenzwert wird gezeigt",
            f"{entity_id} auf Stellwert {brightness} "
            f"({level * 100:.0f} % zwischen {min_flux * 100:.0f} und {max_flux * 100:.0f} %)",
        )
        return brightness

    async def restore_zone(self, zone_id: str) -> bool:
        """Stellt nach einer Vorschau wieder her, was der Stapel sagt."""
        runtime = self.zones.get(zone_id)
        if runtime is None:
            return False
        await self._apply(runtime, "Nach der Vorschau")
        return True

    async def preview(self, zone_id: str, levels: dict[str, float]) -> bool:
        """Live-Vorschau im Szenen-Editor — ohne Anmeldung im Stapel."""
        runtime = self.zones.get(zone_id)
        if runtime is None:
            return False
        commands = resolve_scene(runtime.zone, levels, fade=0.4, reason="Vorschau")
        await self.driver.apply(commands, zone_id)
        return True

    async def turn_off(self, zone_id: str, source: str = "Panel") -> bool:
        runtime = self.zones.get(zone_id)
        if runtime is None:
            return False
        runtime.stack.release_above(LAYER_BASE)
        runtime.blocked_until = time.monotonic() + BLOCK_AFTER_MANUAL_OFF
        runtime.state = STATE_EMPTY
        await self._apply(runtime, f"{source}: aus")
        return True

    async def next_scene(self, zone_id: str, source: str = "Taster") -> bool:
        """Blättert durch die Szenen der Zone — das Durchtipp-Muster."""
        runtime = self.zones.get(zone_id)
        if runtime is None or not runtime.zone.scenes:
            return False
        active = runtime.stack.active
        ids = [s.id for s in runtime.zone.scenes]
        if active is None or active.scene_id not in ids:
            return await self.apply_scene(zone_id, ids[0], source)
        index = ids.index(active.scene_id)
        if index + 1 >= len(ids):
            return await self.turn_off(zone_id, source)
        return await self.apply_scene(zone_id, ids[index + 1], source)

    async def release_layer(self, zone_id: str, layer: int) -> bool:
        runtime = self.zones.get(zone_id)
        if runtime is None:
            return False
        runtime.stack.release(layer)
        await self._apply(runtime, f"Ebene {layer} freigegeben")
        return True

    def snapshot_levels(self, zone_id: str) -> dict[str, float]:
        """Liest den Ist-Zustand der Zone als Sollwerte zurück.

        Damit lässt sich eine von Hand eingestellte Lichtstimmung als Szene
        übernehmen, statt Prozentwerte zu raten. Gerechnet wird über die
        Dimmkurve der jeweiligen Leuchte.
        """
        runtime = self.zones.get(zone_id)
        if runtime is None:
            return {}

        out: dict[str, float] = {}
        for circuit in runtime.zone.circuits:
            values = []
            for fixture in circuit.fixtures:
                state = self.hass.states.get(fixture.entity_id)
                if state is None or state.state != "on":
                    values.append(0.0)
                    continue
                brightness = state.attributes.get("brightness")
                if brightness is None:
                    values.append(1.0)
                    continue
                values.append(
                    brightness_to_level(
                        int(brightness),
                        fixture.curve,
                        fixture.min_flux,
                        fixture.max_flux,
                    )
                )
            out[circuit.id] = round(max(values) if values else 0.0, 3)
        return out

    def snapshot_kelvin(self, zone_id: str) -> dict[str, int]:
        """Farbtemperaturen des Ist-Zustands je Lichtkreis."""
        runtime = self.zones.get(zone_id)
        if runtime is None:
            return {}
        out: dict[str, int] = {}
        for circuit in runtime.zone.circuits:
            for fixture in circuit.fixtures:
                state = self.hass.states.get(fixture.entity_id)
                if state is None or state.state != "on":
                    continue
                kelvin = state.attributes.get("color_temp_kelvin")
                if kelvin:
                    out[circuit.id] = int(kelvin)
                    break
        return out

    # -- Zustand für die Oberfläche ----------------------------------------

    def zone_state(self, zone_id: str) -> dict[str, Any]:
        runtime = self.zones.get(zone_id)
        if runtime is None:
            return {}
        now = time.monotonic()
        levels, kelvin, _ = runtime.stack.resolve()
        active = runtime.stack.active
        return {
            "id": zone_id,
            "name": runtime.zone.name,
            "state": runtime.state,
            "lux": runtime.last_lux,
            "occupied": runtime.occupied(now),
            "master": round(max(levels.values()) if levels else 0.0, 3),
            "levels": {k: round(v, 3) for k, v in levels.items()},
            "kelvin": kelvin,
            "layer": active.layer if active else None,
            "layer_source": active.source if active else "",
            "remaining": active.remaining(now) if active else None,
            "stack": runtime.stack.snapshot(now),
            "scene_id": active.scene_id if active else None,
            "faults": sorted(
                f for f in self.driver.stats.faults if f in runtime.zone.entity_ids
            ),
            "daylight": {
                "aktiv": runtime.zone.daylight,
                "kelvin": (runtime.last_daylight or (0, 0))[0],
                "faktor": (runtime.last_daylight or (0, 0))[1],
                "kurve": runtime.zone.curve_key
                or KIND_TO_CURVE.get(runtime.zone.kind, "wohnen"),
            },
            "konstantlicht": {
                "aktiv": runtime.zone.constant_light,
                "kalibriert": bool(
                    runtime.calibration and runtime.calibration.valid
                ),
                "faktor": round(runtime.control_factor, 3),
                "sollwert": runtime.zone.setpoint_lux,
            },
        }

    def overview(self) -> dict[str, Any]:
        return {
            "mode": self.installation.mode,
            "zones": [self.zone_state(z) for z in self.zones],
            "stats": {
                "calls": self.driver.stats.calls,
                "skipped": self.driver.stats.skipped,
                "grouped": self.driver.stats.grouped,
                "retries": self.driver.stats.retries,
                "faults": sorted(self.driver.stats.faults),
            },
        }

    # -- Benachrichtigung der Oberfläche -----------------------------------

    def subscribe(self, callback_fn: Callable[[str, dict], None]) -> Callable[[], None]:
        self._listeners.append(callback_fn)

        def unsubscribe() -> None:
            if callback_fn in self._listeners:
                self._listeners.remove(callback_fn)

        return unsubscribe

    def _notify(self, kind: str, payload: dict) -> None:
        for listener in list(self._listeners):
            try:
                listener(kind, payload)
            except Exception:  # noqa: BLE001
                self._listeners.remove(listener)


def get_engine(hass: HomeAssistant) -> Engine | None:
    return hass.data.get(DOMAIN, {}).get("engine")
