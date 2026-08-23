"""Tests des Szenengenerators und der Auflösung auf Stellwerte."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: E402

from lichtregie.core.model import (  # noqa: E402
    Circuit,
    Fixture,
    Zone,
)
from lichtregie.core.scenes import (  # noqa: E402
    dim_factor,
    resolve_scene,
    suggest_scenes,
)

GENERAL, TASK, AMBIENT, ACCENT, NIGHT = (
    "general",
    "task",
    "ambient",
    "accent",
    "night",
)


def fixture(entity_id: str, **kw) -> Fixture:
    base = {
        "dimmable": True,
        "color_temp": True,
        "min_kelvin": 2200,
        "max_kelvin": 6500,
        "min_flux": 0.01,
        "max_flux": 1.0,
        "curve": "log",
    }
    base.update(kw)
    return Fixture(entity_id=entity_id, name=entity_id, **base)


def living_room() -> Zone:
    """Nachbau des Wohnzimmers: Grund, Stimmung, Akzent, Arbeit."""
    return Zone(
        id="wohnzimmer",
        name="Wohnzimmer",
        kind="wohnraum",
        circuits=[
            Circuit(
                "k1",
                "Deckenspots",
                GENERAL,
                [fixture("light.spots", color_temp=False)],
            ),
            Circuit("k2", "Lichtvoute", AMBIENT, [fixture("light.voute", night_capable=True)]),
            Circuit("k3", "Dekolampe", ACCENT, [fixture("light.deko")]),
            Circuit("k4", "Leseleuchte", TASK, [fixture("light.lese")]),
            Circuit("k5", "Hue unten", ACCENT, [fixture("light.hue_u", glares=True)]),
        ],
    )


def hallway() -> Zone:
    """Flur: nur Grundlicht, kein Stimmungs- oder Arbeitslicht."""
    return Zone(
        id="flur",
        name="Flur",
        kind="verkehrsweg",
        circuits=[Circuit("k1", "Spots", GENERAL, [fixture("light.flur")])],
    )


# --- Vorschläge ------------------------------------------------------------


def test_living_room_gets_the_full_set():
    names = {s.id for s in suggest_scenes(living_room())}
    assert {"ankommen", "lesen", "fernsehen", "entspannen", "putzen"} <= names


def test_hallway_gets_only_what_it_can_do():
    """Ohne Stimmungslicht kein Fernsehen und kein Entspannen."""
    names = {s.id for s in suggest_scenes(hallway())}
    assert "durchgang" in names
    assert "ankommen" in names
    assert "fernsehen" not in names
    assert "lesen" not in names


def test_room_type_filters_scenes():
    """Durchgang gibt es im Verkehrsweg, nicht im Wohnraum."""
    assert "durchgang" not in {s.id for s in suggest_scenes(living_room())}
    assert "durchgang" in {s.id for s in suggest_scenes(hallway())}


def test_night_scene_falls_back_to_ambient():
    """Ohne Orientierungslicht springt das Stimmungslicht stark gedimmt ein."""
    zone = living_room()  # hat keinen night-Kreis
    scenes = {s.id: s for s in suggest_scenes(zone)}
    assert "nachtgang" in scenes
    step = scenes["nachtgang"].steps[0]
    assert step.circuit_id == "k2"  # die Voute
    assert step.level <= 0.05


def test_mehrere_rollen_je_kreis():
    """Die Dekolampe ist Akzent und nachts Orientierung."""
    zone = living_room()
    deko = zone.circuits[2]
    deko.roles = [ACCENT, NIGHT]
    scenes = {s.id: s for s in suggest_scenes(zone)}
    # Als Orientierung trägt sie die Nachtszene …
    assert scenes["nachtgang"].level_of(deko.id) > 0
    # … und als Akzent das Fernsehen.
    assert scenes["fernsehen"].level_of(deko.id) > 0


def test_kreis_erscheint_nur_einmal_je_szene():
    """Trifft eine Szene zwei Rollen desselben Kreises, gilt der höhere Wert."""
    zone = living_room()
    kreis = zone.circuits[1]
    kreis.roles = [AMBIENT, ACCENT]
    szene = {s.id: s for s in suggest_scenes(zone)}["entspannen"]
    treffer = [st for st in szene.steps if st.circuit_id == kreis.id]
    assert len(treffer) == 1
    # Akzent (0.60) schlägt Stimmung (0.45)
    assert treffer[0].level == 0.6


def test_suggestions_never_overwrite():
    zone = living_room()
    zone.scenes = suggest_scenes(zone)
    again = suggest_scenes(zone)
    assert again == []


def test_scene_levels_are_sane():
    for scene in suggest_scenes(living_room()):
        for step in scene.steps:
            assert 0.0 < step.level <= 1.0, (scene.id, step)


# --- Auflösung -------------------------------------------------------------


def test_resolve_sets_brightness_and_kelvin():
    zone = living_room()
    cmds = {c.entity_id: c for c in resolve_scene(zone, {"k1": 0.5, "k4": 1.0}, {"k4": 4000})}
    assert cmds["light.spots"].on and cmds["light.spots"].brightness > 0
    assert cmds["light.lese"].kelvin == 4000
    # Kreise ohne Sollwert werden ausgeschaltet
    assert cmds["light.deko"].on is False


def test_resolve_respects_fixture_kelvin_range():
    zone = living_room()
    zone.circuits[0].fixtures[0] = fixture("light.spots", min_kelvin=2700, max_kelvin=4000)
    cmds = {c.entity_id: c for c in resolve_scene(zone, {"k1": 1.0}, {"k1": 6500})}
    assert cmds["light.spots"].kelvin == 4000


def test_resolve_skips_kelvin_for_plain_dimmers():
    zone = living_room()
    zone.circuits[0].fixtures[0] = fixture("light.spots", color_temp=False)
    cmds = {c.entity_id: c for c in resolve_scene(zone, {"k1": 1.0}, {"k1": 4000})}
    assert cmds["light.spots"].kelvin is None


def test_farbtemperatur_abschaltbar():
    """Manche Leuchten sollen ihre Farbe behalten, obwohl sie es könnten."""
    zone = living_room()
    zone.circuits[3].fixtures[0] = fixture("light.lese", manage_color=False)
    cmds = {c.entity_id: c for c in resolve_scene(zone, {"k4": 1.0}, {"k4": 4000})}
    assert cmds["light.lese"].kelvin is None


def test_maximalhelligkeit_begrenzt():
    """Sein Fall: die meisten Leuchten laufen höchstens auf 40 Prozent."""
    zone = hallway()
    zone.circuits[0].fixtures[0] = fixture("light.flur", max_flux=0.40)
    voll = resolve_scene(zone, {"k1": 1.0})[0].brightness
    assert voll == round(0.40 * 255)


def test_night_blocks_glaring_and_non_night_circuits():
    zone = living_room()
    cmds = {
        c.entity_id: c
        for c in resolve_scene(zone, {"k1": 0.5, "k2": 0.04, "k5": 0.5}, night=True)
    }
    assert cmds["light.voute"].on is True  # night_capable
    assert cmds["light.spots"].on is False  # nicht nachtfähig
    assert cmds["light.hue_u"].on is False  # blendet


def test_dim_factor_curve():
    assert dim_factor(0, 30, 300) == 1.0
    assert dim_factor(30, 30, 300) == 1.0
    assert dim_factor(400, 30, 300) == 0.0
    mid = dim_factor(165, 30, 300, factor_min=0.4)
    assert 0.65 < mid < 0.75
    assert dim_factor(None, 30, 300) == 1.0


def test_dim_factor_scales_output():
    zone = hallway()
    bright = resolve_scene(zone, {"k1": 1.0}, dim_factor=1.0)[0].brightness
    dimmed = resolve_scene(zone, {"k1": 1.0}, dim_factor=0.5)[0].brightness
    assert dimmed < bright


def test_non_dimmable_gets_full_value():
    zone = hallway()
    zone.circuits[0].fixtures[0] = fixture("light.flur", dimmable=False)
    assert resolve_scene(zone, {"k1": 0.2})[0].brightness == 255


def test_fade_zero_when_device_cannot_transition():
    zone = hallway()
    zone.circuits[0].fixtures[0] = fixture("light.flur", supports_transition=False)
    assert resolve_scene(zone, {"k1": 0.5}, fade=2.0)[0].fade == 0.0


def test_disabled_circuit_is_untouched():
    zone = hallway()
    zone.circuits[0].enabled = False
    assert resolve_scene(zone, {"k1": 1.0}) == []


if __name__ == "__main__":
    sys.exit(_bootstrap.run(globals()))
