"""Alte Fassungen der Konfiguration überführen.

Bis Fassung 0.3 speicherte eine Szene einen Wert je Lichtkreis. Seit 0.4
steht der Wert je Rolle, mit Ausnahmen für einzelne Kreise. Diese Datei
rechnet den alten Bestand um, ohne das Lichtbild zu verändern.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

__all__ = ["scene_from_steps", "migrate_installation"]


def scene_from_steps(
    steps: list[dict[str, Any]],
    circuits: list[dict[str, Any]],
) -> tuple[dict[str, float], dict[str, float], int | None]:
    """Rechnet Werte je Lichtkreis in Werte je Rolle plus Ausnahmen um.

    Für jede Rolle gilt der häufigste Wert unter ihren Kreisen; bei
    Gleichstand der hellere. Jeder Kreis, der davon abweicht, wird zur
    Ausnahme — auch mit Wert 0, wenn er in der Szene gar nicht vorkam,
    seine Rolle aber leuchtet.
    """
    werte = {s["circuit_id"]: float(s.get("level", 0.0)) for s in steps}
    kelvin_werte = [s.get("kelvin") for s in steps if s.get("kelvin")]
    kelvin = kelvin_werte[0] if kelvin_werte else None

    # Rollen je Kreis, wie sie in der Zone stehen.
    rollen_je_kreis: dict[str, list[str]] = {}
    for c in circuits:
        rollen = c.get("roles") or [c.get("role", "general")]
        rollen_je_kreis[c["id"]] = [r for r in rollen if r]

    # Kandidaten je Rolle sammeln — nur Kreise, die in der Szene stehen.
    je_rolle: dict[str, list[float]] = {}
    for circuit_id, level in werte.items():
        for rolle in rollen_je_kreis.get(circuit_id, []):
            je_rolle.setdefault(rolle, []).append(level)

    levels: dict[str, float] = {}
    for rolle, liste in je_rolle.items():
        haeufig = Counter(liste).most_common()
        spitze = haeufig[0][1]
        levels[rolle] = max(w for w, anzahl in haeufig if anzahl == spitze)

    # Ausnahmen: alles, was der Rollenwert nicht trifft.
    overrides: dict[str, float] = {}
    for circuit_id, rollen in rollen_je_kreis.items():
        aus_rolle = max(
            [levels.get(r, 0.0) for r in rollen] or [0.0]
        )
        tatsaechlich = werte.get(circuit_id, 0.0)
        if abs(tatsaechlich - aus_rolle) > 0.001:
            overrides[circuit_id] = round(tatsaechlich, 3)

    return (
        {k: round(v, 3) for k, v in levels.items() if v > 0},
        overrides,
        kelvin,
    )


def migrate_installation(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Überführt eine gespeicherte Anlage in die neue Szenenform.

    Rückgabe sind die Daten und die Zahl der umgerechneten Szenen.
    """
    umgerechnet = 0
    for zone in data.get("zones", []):
        for scene in zone.get("scenes", []):
            if "steps" not in scene or scene.get("levels"):
                continue
            levels, overrides, kelvin = scene_from_steps(
                scene.get("steps") or [], zone.get("circuits") or []
            )
            scene["levels"] = levels
            scene["overrides"] = overrides
            if kelvin and not scene.get("kelvin"):
                scene["kelvin"] = kelvin
            scene.pop("steps", None)
            umgerechnet += 1
    return data, umgerechnet
