"""Bindungen: was ein Auslöser bewirkt.

Eine Bindung besteht aus fünf Teilen — Auslöser, Bedingung, Ebene,
Haltedauer, Danach. Dieses Modul enthält die Prüfung der Bedingungen, die
Berechnung der Ablaufzeit und die Belegungsvorlagen für Taster.

Alles hier ist reine Rechnung: die Zeit und der Zustand werden übergeben.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..const import (
    GESTURE_DOUBLE,
    GESTURE_LONG,
    GESTURE_TAP,
    HOLD_FIXED,
    HOLD_FOREVER,
    HOLD_UNTIL_EMPTY,
    HOLD_UNTIL_PRESS,
    HOLD_UNTIL_SCENE,
    HOLD_UNTIL_TIME,
    HOLD_WHILE_OCCUPIED,
    LAYER_PRESENCE,
    LAYER_SCENE,
    STATE_EXTENDED,
    STATE_NIGHT,
    STATE_OCCUPIED,
)
from .model import Binding, Zone

__all__ = [
    "Context",
    "conditions_hold",
    "expiry_for",
    "TEMPLATES",
    "apply_template",
    "describe",
]


@dataclass
class Context:
    """Was zur Prüfung einer Bedingung bekannt sein muss."""

    now: float = 0.0
    lux: float | None = None
    state: str = ""
    mode: str = "normal"
    night: bool = False
    occupied: bool = False
    weekday: int = 0  # 0 = Montag
    minute_of_day: int = 720


def _in_window(start: str, end: str, minute: int) -> bool:
    """Zeitfenster prüfen — auch über Mitternacht hinweg."""

    def to_minutes(value: str) -> int:
        hour, _, rest = value.partition(":")
        return int(hour) * 60 + int(rest or 0)

    begin, finish = to_minutes(start), to_minutes(end)
    if begin <= finish:
        return begin <= minute <= finish
    return minute >= begin or minute <= finish


def conditions_hold(binding: Binding, context: Context) -> tuple[bool, str]:
    """Prüft alle Bedingungen einer Bindung.

    Rückgabe ist das Ergebnis und die Begründung fürs Protokoll — auch im
    positiven Fall, damit im Protokoll steht, warum etwas geschaltet hat.
    """
    conditions = binding.conditions or {}

    max_lux = conditions.get("max_lux")
    if max_lux is not None and context.lux is not None:
        if context.lux > float(max_lux):
            return False, f"Fremdlicht {context.lux:.0f} lx über Grenze {float(max_lux):.0f} lx"

    min_lux = conditions.get("min_lux")
    if min_lux is not None and context.lux is not None:
        if context.lux < float(min_lux):
            return False, f"Fremdlicht {context.lux:.0f} lx unter Grenze {float(min_lux):.0f} lx"

    night_only = conditions.get("nur_nachts")
    if night_only is not None and bool(night_only) != context.night:
        return False, "Nachtfenster passt nicht"

    mode = conditions.get("betriebsart")
    if mode and mode != context.mode:
        return False, f"Betriebsart ist {context.mode}, verlangt {mode}"

    needed = conditions.get("ab_zustand")
    if needed:
        order = {"": 0, "leer": 0, "ankunft": 1, STATE_OCCUPIED: 2, STATE_EXTENDED: 3}
        if order.get(context.state, 0) < order.get(needed, 0):
            return False, f"Zustand {context.state} vor {needed}"

    window = conditions.get("zeitfenster")
    if window and not _in_window(
        window.get("von", "00:00"), window.get("bis", "23:59"), context.minute_of_day
    ):
        return False, "außerhalb des Zeitfensters"

    days = conditions.get("wochentage")
    if days and context.weekday not in days:
        return False, "heute nicht vorgesehen"

    if conditions.get("nur_wenn_leer") and context.occupied:
        return False, "Zone ist belegt"

    return True, "Bedingungen erfüllt"


def expiry_for(binding: Binding, zone: Zone, context: Context) -> float | None:
    """Wann die Anmeldung dieser Bindung abläuft.

    ``None`` heißt: läuft nicht von selbst ab. Die Freigabe kommt dann aus
    dem Zustandsautomaten oder von einer Taste.
    """
    now = context.now

    if binding.hold == HOLD_FIXED:
        return now + float(binding.hold_seconds or 1800.0)

    if binding.hold == HOLD_WHILE_OCCUPIED:
        return now + float(binding.hold_seconds or zone.linger)

    if binding.hold in (HOLD_UNTIL_EMPTY, HOLD_UNTIL_PRESS, HOLD_UNTIL_SCENE, HOLD_FOREVER):
        return None

    if binding.hold == HOLD_UNTIL_TIME:
        target = binding.until or "23:00"
        hour, _, rest = target.partition(":")
        target_minute = int(hour) * 60 + int(rest or 0)
        delta = (target_minute - context.minute_of_day) % 1440
        return now + max(60.0, delta * 60.0)

    return now + zone.linger


# --------------------------------------------------------------------------
# Belegungsvorlagen für Taster
# --------------------------------------------------------------------------


def _binding(
    button: str,
    gesture: str,
    action: str,
    scene_id: str | None = None,
    layer: int = LAYER_SCENE,
    hold: str = HOLD_UNTIL_EMPTY,
    hold_seconds: float | None = None,
) -> Binding:
    return Binding(
        id=f"{button}_{gesture}",
        trigger={"art": "taste", "taste": button, "geste": gesture},
        action=action,
        scene_id=scene_id,
        layer=layer,
        hold=hold,
        hold_seconds=hold_seconds,
    )


def _template_classic(buttons: list[str], scenes: list[str]) -> list[Binding]:
    """Links aus, rechts Grundszene, langer Druck alles aus.

    Das Muster, das jeder ohne Erklärung bedienen kann.
    """
    out: list[Binding] = []
    if not buttons:
        return out
    first = buttons[0]
    second = buttons[1] if len(buttons) > 1 else buttons[0]

    if scenes:
        out.append(_binding(first, GESTURE_TAP, "scene", scenes[0]))
        if len(scenes) > 1:
            out.append(
                _binding(
                    first,
                    GESTURE_DOUBLE,
                    "scene",
                    scenes[1],
                    hold=HOLD_FIXED,
                    hold_seconds=1200.0,
                )
            )
    out.append(_binding(second, GESTURE_TAP, "zone_aus"))
    out.append(_binding(second, GESTURE_LONG, "etage_aus"))
    return out


def _template_cycle(buttons: list[str], scenes: list[str]) -> list[Binding]:
    """Eine Taste blättert durch die Szenen — der Durchtipp-Umschalter."""
    out: list[Binding] = []
    if not buttons:
        return out
    first = buttons[0]
    second = buttons[1] if len(buttons) > 1 else buttons[0]
    out.append(_binding(first, GESTURE_TAP, "weiter"))
    out.append(_binding(first, GESTURE_LONG, "automatik", layer=LAYER_PRESENCE))
    out.append(_binding(second, GESTURE_TAP, "zone_aus"))
    return out


def _template_direct(buttons: list[str], scenes: list[str]) -> list[Binding]:
    """Jede Taste eine feste Szene, letzte Taste aus."""
    out: list[Binding] = []
    usable = buttons[:-1] if len(buttons) > 1 else buttons
    for button, scene_id in zip(usable, scenes):
        out.append(_binding(button, GESTURE_TAP, "scene", scene_id))
    if len(buttons) > 1:
        out.append(_binding(buttons[-1], GESTURE_TAP, "zone_aus"))
        out.append(_binding(buttons[-1], GESTURE_LONG, "etage_aus"))
    return out


def _template_night(buttons: list[str], scenes: list[str]) -> list[Binding]:
    """Für das Schlafzimmer: tagsüber Szene, nachts nur Orientierung."""
    out: list[Binding] = []
    if not buttons or not scenes:
        return out
    first = buttons[0]
    second = buttons[1] if len(buttons) > 1 else buttons[0]
    day = _binding(first, GESTURE_TAP, "scene", scenes[0])
    day.conditions = {"nur_nachts": False}
    out.append(day)
    night_scene = "nachtgang" if "nachtgang" in scenes else scenes[-1]
    night = _binding(first, GESTURE_TAP, "scene", night_scene)
    night.id = f"{first}_{GESTURE_TAP}_nacht"
    night.conditions = {"nur_nachts": True}
    out.append(night)
    out.append(_binding(second, GESTURE_TAP, "zone_aus"))
    return out


TEMPLATES: dict[str, dict[str, Any]] = {
    "klassisch": {
        "name": "Klassisch",
        "beschreibung": "Rechts an, links aus, doppelt für hell, lang für Etage aus.",
        "build": _template_classic,
    },
    "durchtippen": {
        "name": "Durchtippen",
        "beschreibung": "Eine Taste blättert durch die Szenen, lang schaltet die Automatik scharf.",
        "build": _template_cycle,
    },
    "direktwahl": {
        "name": "Direktwahl",
        "beschreibung": "Jede Taste eine feste Szene, letzte Taste aus.",
        "build": _template_direct,
    },
    "tagnacht": {
        "name": "Tag und Nacht",
        "beschreibung": "Dieselbe Taste schaltet nachts nur das Orientierungslicht.",
        "build": _template_night,
    },
}


def apply_template(key: str, buttons: list[str], scenes: list[str]) -> list[Binding]:
    """Erzeugt eine Tastenbelegung aus einer Vorlage."""
    template = TEMPLATES.get(key)
    if template is None:
        return []
    return template["build"](buttons, scenes)


def describe(binding: Binding, zone: Zone | None = None) -> str:
    """Eine Zeile Klartext für die Oberfläche und das Protokoll."""
    actions = {
        "zone_aus": "Zone aus",
        "etage_aus": "Etage aus",
        "automatik": "Automatik scharf",
        "weiter": "nächste Szene",
        "dimmen": "dimmen",
    }
    if binding.action in actions:
        what = actions[binding.action]
    else:
        scene = zone.scene(binding.scene_id or "") if zone else None
        what = f"Szene „{scene.name}“" if scene else f"Szene {binding.scene_id}"

    holds = {
        HOLD_WHILE_OCCUPIED: "solange belegt",
        HOLD_FIXED: (
            f"{(binding.hold_seconds or 1800) / 60:.0f} min"
            if binding.hold_seconds
            else "feste Dauer"
        ),
        HOLD_UNTIL_EMPTY: "bis Zone leer",
        HOLD_UNTIL_PRESS: "bis Gegendruck",
        HOLD_UNTIL_TIME: f"bis {binding.until or '23:00'}",
        HOLD_UNTIL_SCENE: "bis andere Szene",
        HOLD_FOREVER: "unbegrenzt",
    }
    hold = holds.get(binding.hold, binding.hold)
    return f"{what} · Ebene {binding.layer} · {hold}"
