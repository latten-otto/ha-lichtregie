"""Tests der Umstellung alter Szenen auf Rollenwerte.

Entscheidend ist nur eines: das Lichtbild darf sich nicht ändern. Was
vorher je Lichtkreis gespeichert war, muss nach der Umrechnung über
Rollenwerte und Ausnahmen exakt dieselben Werte ergeben.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: E402

from lichtregie.core.migrate import migrate_installation, scene_from_steps  # noqa: E402
from lichtregie.core.model import Circuit, Fixture, Scene, Zone  # noqa: E402


def wohnzimmer() -> Zone:
    """Nachbau mit vier Stimmungsleuchten — der Fall, um den es geht."""
    return Zone(
        id="wz",
        name="Wohnzimmer",
        circuits=[
            Circuit("k1", "Deckenspots", "general", [Fixture("light.spots")]),
            Circuit("k2", "Wandlampe 1", "ambient", [Fixture("light.w1")]),
            Circuit("k3", "Wandlampe 2", "ambient", [Fixture("light.w2")]),
            Circuit("k4", "Wandlampe 3", "ambient", [Fixture("light.w3")]),
            Circuit("k5", "Wandlampe 4", "ambient", [Fixture("light.w4")]),
            Circuit("k6", "Dekolampe", ["accent", "night"], [Fixture("light.deko")]),
        ],
    )


def als_dicts(zone: Zone) -> list[dict]:
    return [c.to_dict() for c in zone.circuits]


def steps(**werte) -> list[dict]:
    return [{"circuit_id": k, "level": v} for k, v in werte.items()]


# --- Umrechnung ------------------------------------------------------------


def test_gleiche_werte_werden_zur_rolle():
    """Vier Wandlampen auf 45 % ergeben einen Rollenwert, keine Ausnahmen."""
    levels, overrides, _ = scene_from_steps(
        steps(k1=0.15, k2=0.45, k3=0.45, k4=0.45, k5=0.45),
        als_dicts(wohnzimmer()),
    )
    assert levels["ambient"] == 0.45
    assert levels["general"] == 0.15
    assert overrides == {}


def test_abweichung_wird_ausnahme():
    """Eine Wandlampe anders als die übrigen — genau dafür sind Ausnahmen da."""
    levels, overrides, _ = scene_from_steps(
        steps(k2=0.45, k3=0.45, k4=0.45, k5=0.20),
        als_dicts(wohnzimmer()),
    )
    assert levels["ambient"] == 0.45
    assert overrides == {"k5": 0.2}


def test_fehlender_kreis_wird_ausnahme_mit_null():
    """War ein Kreis nicht in der Szene, darf ihn die Rolle nicht anschalten."""
    levels, overrides, _ = scene_from_steps(
        steps(k2=0.45, k3=0.45, k4=0.45),
        als_dicts(wohnzimmer()),
    )
    assert levels["ambient"] == 0.45
    assert overrides["k5"] == 0.0


def test_gleichstand_nimmt_den_helleren():
    levels, _, _ = scene_from_steps(
        steps(k2=0.6, k3=0.6, k4=0.3, k5=0.3), als_dicts(wohnzimmer())
    )
    assert levels["ambient"] == 0.6


def test_farbtemperatur_wird_uebernommen():
    _, _, kelvin = scene_from_steps(
        [{"circuit_id": "k1", "level": 0.5, "kelvin": 2700}],
        als_dicts(wohnzimmer()),
    )
    assert kelvin == 2700


# --- Das Entscheidende: gleiches Lichtbild ---------------------------------


def probe(**werte) -> None:
    """Rechnet um und prüft, dass jeder Kreis denselben Wert behält."""
    zone = wohnzimmer()
    levels, overrides, _ = scene_from_steps(steps(**werte), als_dicts(zone))
    scene = Scene(id="s", name="S", levels=levels, overrides=overrides)
    nachher = scene.resolve(zone)
    vorher = {k: v for k, v in werte.items() if v > 0}
    assert nachher == vorher, f"vorher {vorher} · nachher {nachher}"


def test_lichtbild_bleibt_gleich_einfach():
    probe(k1=0.15, k2=0.45, k3=0.45, k4=0.45, k5=0.45)


def test_lichtbild_bleibt_gleich_mit_ausnahme():
    probe(k1=0.15, k2=0.45, k3=0.45, k4=0.45, k5=0.20)


def test_lichtbild_bleibt_gleich_bei_luecken():
    probe(k1=0.6, k2=0.4, k5=0.4)


def test_lichtbild_bleibt_gleich_bei_mehrfachrolle():
    """Die Dekolampe ist Akzent und Orientierung zugleich."""
    probe(k1=0.15, k2=0.45, k3=0.45, k4=0.45, k5=0.45, k6=0.6)


def test_lichtbild_bleibt_gleich_wenn_alles_verschieden():
    probe(k1=0.1, k2=0.2, k3=0.3, k4=0.4, k5=0.5, k6=0.6)


def test_leere_szene_bleibt_leer():
    zone = wohnzimmer()
    levels, overrides, _ = scene_from_steps([], als_dicts(zone))
    assert Scene(id="s", name="S", levels=levels, overrides=overrides).resolve(zone) == {}


# --- Ganze Anlage ----------------------------------------------------------


def test_installation_wird_umgerechnet():
    daten = {
        "zones": [
            {
                "id": "wz",
                "name": "Wohnzimmer",
                "circuits": als_dicts(wohnzimmer()),
                "scenes": [
                    {
                        "id": "entspannen",
                        "name": "Entspannen",
                        "fade": 3.0,
                        "steps": steps(k1=0.15, k2=0.45, k3=0.45, k4=0.45, k5=0.45),
                    }
                ],
            }
        ]
    }
    daten, anzahl = migrate_installation(daten)
    assert anzahl == 1
    scene = daten["zones"][0]["scenes"][0]
    assert "steps" not in scene
    assert scene["levels"]["ambient"] == 0.45
    assert scene["fade"] == 3.0


def test_bereits_umgestellte_szene_bleibt_unberuehrt():
    daten = {
        "zones": [
            {
                "id": "wz",
                "circuits": als_dicts(wohnzimmer()),
                "scenes": [{"id": "s", "name": "S", "levels": {"ambient": 0.5}}],
            }
        ]
    }
    _, anzahl = migrate_installation(daten)
    assert anzahl == 0


def test_migration_laeuft_nur_einmal():
    daten = {
        "zones": [
            {
                "id": "wz",
                "circuits": als_dicts(wohnzimmer()),
                "scenes": [{"id": "s", "name": "S", "steps": steps(k2=0.4)}],
            }
        ]
    }
    daten, erste = migrate_installation(daten)
    daten, zweite = migrate_installation(daten)
    assert erste == 1 and zweite == 0


if __name__ == "__main__":
    sys.exit(_bootstrap.run(globals()))
