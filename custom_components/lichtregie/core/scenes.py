"""Szenenvorschläge und Auflösung auf Stellwerte.

Kein maschinelles Lernen, sondern ein Regelwerk: Raumtyp und vorhandene
Rollen ergeben eine Menge sinnvoller Lichtstimmungen. Fehlt eine Rolle,
entfällt die Szene oder ihr Anteil wird umverteilt.

Zielhelligkeiten und Farbtemperaturen folgen den Empfehlungen für
Wohnraumbeleuchtung nach DIN EN 12464-1 sowie den Planungsempfehlungen für
biologisch wirksame Beleuchtung.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..const import (
    ROLE_ACCENT,
    ROLE_AMBIENT,
    ROLE_GENERAL,
    ROLE_NIGHT,
    ROLE_TASK,
)
from .model import Circuit, Scene, SceneStep, Zone
from .photometry import fit_kelvin, level_to_brightness

__all__ = ["Intent", "INTENTS", "suggest_scenes", "resolve_scene", "Command"]

KELVIN_DAYLIGHT = "hcl"  # Platzhalter: Farbe kommt aus dem Tagesverlauf


@dataclass(frozen=True)
class Intent:
    """Eine Szenenabsicht als Sollwerte je Rolle."""

    key: str
    name: str
    levels: dict[str, float]
    kelvin: int | str = KELVIN_DAYLIGHT
    requires: frozenset[str] = frozenset()
    fade: float = 1.5
    follows_daylight: bool = False
    max_lux: float | None = None
    min_state: str | None = None
    kinds: frozenset[str] = frozenset()  # leer heißt: für jeden Raumtyp


INTENTS: tuple[Intent, ...] = (
    Intent(
        key="ankommen",
        name="Ankommen",
        levels={ROLE_GENERAL: 0.60, ROLE_AMBIENT: 0.40},
        requires=frozenset({ROLE_GENERAL}),
        follows_daylight=True,
        fade=1.5,
    ),
    Intent(
        key="durchgang",
        name="Durchgang",
        levels={ROLE_GENERAL: 0.45},
        requires=frozenset({ROLE_GENERAL}),
        follows_daylight=True,
        fade=0.3,
        kinds=frozenset({"verkehrsweg", "nassbereich"}),
    ),
    Intent(
        key="arbeiten",
        name="Arbeiten",
        levels={ROLE_GENERAL: 0.45, ROLE_TASK: 1.00},
        kelvin=4000,
        requires=frozenset({ROLE_TASK}),
        fade=1.0,
    ),
    Intent(
        key="lesen",
        name="Lesen",
        levels={ROLE_GENERAL: 0.35, ROLE_TASK: 1.00, ROLE_AMBIENT: 0.30},
        kelvin=3500,
        requires=frozenset({ROLE_TASK, ROLE_AMBIENT}),
        kinds=frozenset({"wohnraum", "schlafraum"}),
    ),
    Intent(
        key="essen",
        name="Essen",
        levels={ROLE_GENERAL: 0.30, ROLE_TASK: 0.75, ROLE_AMBIENT: 0.45},
        kelvin=2900,
        requires=frozenset({ROLE_TASK}),
        kinds=frozenset({"essraum"}),
    ),
    Intent(
        key="fernsehen",
        name="Fernsehen",
        levels={ROLE_AMBIENT: 0.25, ROLE_ACCENT: 0.40},
        kelvin=2700,
        requires=frozenset({ROLE_AMBIENT}),
        fade=2.0,
        kinds=frozenset({"wohnraum"}),
    ),
    Intent(
        key="entspannen",
        name="Entspannen",
        levels={ROLE_GENERAL: 0.15, ROLE_AMBIENT: 0.45, ROLE_ACCENT: 0.60},
        kelvin=2400,
        requires=frozenset({ROLE_AMBIENT}),
        fade=3.0,
        kinds=frozenset({"wohnraum", "essraum", "schlafraum"}),
    ),
    Intent(
        key="gaeste",
        name="Gäste",
        levels={ROLE_GENERAL: 0.45, ROLE_AMBIENT: 0.60, ROLE_ACCENT: 0.80},
        kelvin=2900,
        requires=frozenset({ROLE_AMBIENT}),
    ),
    Intent(
        key="putzen",
        name="Putzen",
        levels={
            ROLE_GENERAL: 1.00,
            ROLE_TASK: 1.00,
            ROLE_AMBIENT: 1.00,
            ROLE_ACCENT: 1.00,
        },
        kelvin=5000,
        requires=frozenset({ROLE_GENERAL}),
        fade=0.4,
    ),
    Intent(
        key="nachtgang",
        name="Nachtgang",
        levels={ROLE_NIGHT: 0.04},
        kelvin=2200,
        requires=frozenset({ROLE_NIGHT}),
        fade=0.3,
    ),
)

# Wenn eine geforderte Rolle fehlt, darf eine andere einspringen.
_FALLBACK = {
    ROLE_NIGHT: (ROLE_AMBIENT, 0.04),
    ROLE_TASK: (ROLE_GENERAL, 0.90),
    ROLE_AMBIENT: (ROLE_ACCENT, 1.0),
}


def _role_target(zone: Zone, role: str) -> tuple[list[Circuit], float]:
    """Kreise für eine Rolle finden, notfalls über die Ersatzregel."""
    circuits = zone.circuits_with_role(role)
    if circuits:
        return circuits, 1.0
    replacement = _FALLBACK.get(role)
    if replacement:
        other, factor = replacement
        return zone.circuits_with_role(other), factor
    return [], 1.0


def suggest_scenes(zone: Zone) -> list[Scene]:
    """Schlägt Szenen für eine Zone vor.

    Vorhandene Szenen mit gleichem Schlüssel werden nicht überschrieben —
    der Vorschlag ergänzt, er löscht nie.
    """
    have = {s.id for s in zone.scenes}
    roles = zone.roles
    out: list[Scene] = []

    for intent in INTENTS:
        if intent.key in have:
            continue
        if intent.kinds and zone.kind not in intent.kinds:
            continue

        # Geforderte Rollen prüfen — auch über die Ersatzregel.
        missing = [
            role
            for role in intent.requires
            if role not in roles and not _role_target(zone, role)[0]
        ]
        if missing:
            continue

        steps: list[SceneStep] = []
        for role, level in intent.levels.items():
            circuits, factor = _role_target(zone, role)
            for circuit in circuits:
                value = round(min(1.0, level * factor), 3)
                if value > 0:
                    steps.append(
                        SceneStep(
                            circuit_id=circuit.id,
                            level=value,
                            kelvin=(
                                None
                                if intent.kelvin == KELVIN_DAYLIGHT
                                else int(intent.kelvin)
                            ),
                        )
                    )
        if not steps:
            continue

        out.append(
            Scene(
                id=intent.key,
                name=intent.name,
                steps=steps,
                fade=intent.fade,
                follows_daylight=intent.follows_daylight,
                max_lux=intent.max_lux,
                min_state=intent.min_state,
            )
        )
    return out


# --------------------------------------------------------------------------
# Auflösung auf Stellbefehle
# --------------------------------------------------------------------------


@dataclass
class Command:
    """Ein fertiger Stellbefehl für eine Leuchte."""

    entity_id: str
    on: bool
    brightness: int = 0
    kelvin: int | None = None
    fade: float = 1.5
    circuit_id: str = ""
    reason: str = ""

    def key(self) -> tuple:
        """Befehle mit gleichem Schlüssel dürfen zusammengefasst werden."""
        return (self.on, self.brightness, self.kelvin, round(self.fade, 2))


def resolve_scene(
    zone: Zone,
    levels: dict[str, float],
    kelvin: dict[str, int] | None = None,
    *,
    dim_factor: float = 1.0,
    fade: float = 1.5,
    night: bool = False,
    daylight_kelvin: int | None = None,
    reason: str = "",
) -> list[Command]:
    """Rechnet Rollen-Sollwerte auf Stellbefehle je Leuchte um.

    ``dim_factor`` kommt aus der Helligkeitskennlinie der Zone,
    ``night`` sperrt blendende Kreise, ``daylight_kelvin`` ist die
    Farbtemperatur des Tagesverlaufs für Kreise ohne eigene Vorgabe.
    """
    kelvin = kelvin or {}
    commands: list[Command] = []

    for circuit in zone.circuits:
        if not circuit.enabled:
            continue

        level = levels.get(circuit.id, 0.0)

        if night and circuit.glares:
            level = 0.0
        if night and not circuit.night_capable:
            level = 0.0

        level = max(0.0, min(1.0, level * dim_factor))

        if level <= 0.0:
            for fixture in circuit.fixtures:
                commands.append(
                    Command(
                        entity_id=fixture.entity_id,
                        on=False,
                        fade=fade,
                        circuit_id=circuit.id,
                        reason=reason,
                    )
                )
            continue

        target_kelvin = kelvin.get(circuit.id) or daylight_kelvin

        for fixture in circuit.fixtures:
            brightness = (
                level_to_brightness(
                    level, fixture.curve, fixture.min_flux, fixture.max_flux
                )
                if fixture.dimmable
                else 255
            )
            fixture_kelvin = None
            if target_kelvin and (fixture.color_temp or fixture.color):
                fixture_kelvin = int(
                    fit_kelvin(target_kelvin, fixture.min_kelvin, fixture.max_kelvin)
                )
            commands.append(
                Command(
                    entity_id=fixture.entity_id,
                    on=True,
                    brightness=brightness,
                    kelvin=fixture_kelvin,
                    fade=fade if fixture.supports_transition else 0.0,
                    circuit_id=circuit.id,
                    reason=reason,
                )
            )

    return commands


def dim_factor(
    lux: float | None,
    full_below: float,
    off_above: float,
    factor_min: float = 0.4,
) -> float:
    """Kennlinie: je heller die Umgebung, desto weniger Kunstlicht.

    Unterhalb von ``full_below`` volle Szenenwerte, oberhalb von
    ``off_above`` bleibt das Licht aus. Dazwischen linear auf
    ``factor_min`` fallend.
    """
    if lux is None:
        return 1.0
    if lux <= full_below:
        return 1.0
    if lux >= off_above:
        return 0.0
    span = max(1e-6, off_above - full_below)
    share = (lux - full_below) / span
    return max(factor_min, 1.0 - share * (1.0 - factor_min))
