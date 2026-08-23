"""Tests der Rollenerkennung — mit den echten Namen aus der Anlage.

Jeder Fall hier stammt aus einem Trockenlauf über 45 Leuchten. Die
Erkennung ist ein Vorschlag, kein Urteil; sie muss aber die klaren Fälle
treffen und darf vor allem keine Gruppen als Leuchten durchlassen.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: E402

from lichtregie.core.naming import (  # noqa: E402
    KIND_DEFAULTS,
    guess_kind,
    guess_role,
    is_button_trigger,
    is_group,
    is_room_lighting,
    zone_from_name,
)

GENERAL, TASK, AMBIENT, ACCENT, NIGHT = (
    "general",
    "task",
    "ambient",
    "accent",
    "night",
)
DIMMBAR = {"dimmable": True}


def role(name: str) -> str:
    return guess_role(name, DIMMBAR)


# --- Rollen aus echten Namen ----------------------------------------------


def test_grundlicht():
    assert role("Deckenspots Wohnzimmer") == GENERAL
    assert role("Spots Küche") == GENERAL
    assert role("Deckenlicht Esszimmer") == GENERAL
    assert role("Deckenlampe Büro 1") == GENERAL


def test_arbeitslicht():
    assert role("Spülenbeleuchtung") == TASK
    assert role("Kochfeldbeleuchtung") == TASK
    assert role("Kücheninsel spots") == TASK
    assert role("Schlafzimmer Spiegelbeleuchtung") == TASK


def test_pendelleuchte_ist_arbeitslicht():
    """Über dem Esstisch ist die Pendelleuchte Zonenlicht, kein Grundlicht."""
    assert role("Pendelleuchte 1 Esszimmer") == TASK


def test_stimmungslicht():
    assert role("Lichtvoute Wohnzimmer") == AMBIENT
    assert role("Lichtband Badewanne Bad unten") == AMBIENT
    assert role("Wandlampe oben links Wohnzimmer") == AMBIENT
    assert role("Bettbeleuchtung Christian") == AMBIENT


def test_ambiente_schlaegt_arbeitslicht():
    """Der Fall, an dem die alte Reihenfolge scheiterte.

    „Kochinsel Ambientebeleuchtung" enthält „insel" (Arbeitslicht) und
    „ambiente" (Stimmung). Stimmung muss gewinnen.
    """
    assert role("Kochinsel Ambientebeleuchtung") == AMBIENT
    # Ohne das Wort „Ambiente" bleibt es Arbeitslicht.
    assert role("Kücheninsel spots") == TASK


def test_akzentlicht():
    assert role("Dekolampe Wohnzimmer") == ACCENT
    assert role("Schrankbeleuchtung Esszimmer") == ACCENT


def test_orientierungslicht():
    assert role("Nachtlicht Flur") == NIGHT
    assert role("Sockelleuchte Treppe") == NIGHT


def test_unbekanntes_wird_grundlicht():
    assert role("shellyprodm2pm-2cbcbb9ea518 Light 0") == GENERAL
    assert role("Flurschrank") == GENERAL


# --- Keine Raumbeleuchtung -------------------------------------------------


def test_flutlicht_und_kameras_sind_keine_raumbeleuchtung():
    """Sonst stünde beim Szenenaufruf plötzlich der Garten im Scheinwerfer."""
    assert not is_room_lighting("Kamera Hauseingang Flutlicht")
    assert not is_room_lighting("Kamera Norden Flutlicht")
    assert not is_room_lighting("Vorne Flutlicht")


def test_geraetebeleuchtung_ist_keine_raumbeleuchtung():
    assert not is_room_lighting("Luftreiniger Wohnzimmer Hintergrundbeleuchtung")


def test_echte_leuchten_bleiben_raumbeleuchtung():
    for name in (
        "Deckenspots Wohnzimmer",
        "Lichtvoute Wohnzimmer",
        "Wandlampe Bad unten 1",
        "Spülenbeleuchtung",
    ):
        assert is_room_lighting(name), name


# --- Gruppen ---------------------------------------------------------------


class Zustand:
    def __init__(self, **attrs):
        self.attributes = attrs


class Geraet:
    def __init__(self, model):
        self.model = model


def test_ha_lichtgruppe_wird_erkannt():
    """Eine Gruppe würde dieselben Leuchten ein zweites Mal ansteuern."""
    gruppe = Zustand(entity_id=["light.a", "light.b", "light.c"])
    assert is_group(gruppe, None) is True


def test_deconz_gruppe_wird_erkannt():
    assert is_group(Zustand(), Geraet("deCONZ group")) is True


def test_echte_leuchte_ist_keine_gruppe():
    assert is_group(Zustand(brightness=180), Geraet("TRADFRI bulb E14")) is False
    assert is_group(None, None) is False
    assert is_group(Zustand(), None) is False


def test_gruppe_ueber_die_integration():
    """Kurz nach dem Start ist die Mitgliederliste noch leer.

    Dann bliebe die Gruppe unerkannt und würde als eigener Lichtkreis
    angelegt — die Integration der Entität verrät sie trotzdem.
    """
    assert is_group(Zustand(), None, platform="group") is True
    assert is_group(Zustand(), None, platform="light_group") is True
    assert is_group(Zustand(), None, platform="hue") is False


def test_leere_mitgliederliste_ist_keine_gruppe():
    """Ein leeres Attribut zählt nicht — sonst fielen echte Leuchten heraus."""
    assert is_group(Zustand(entity_id=[]), None) is False


# --- Tasterauslöser --------------------------------------------------------
#
# Alle Typen unten stammen aus dem Geräteregister der echten Anlage.


def trg(kind: str) -> bool:
    return is_button_trigger({"type": kind})


def test_busch_jaeger_wandsender():
    """Neun Sender, je 24 Auslöser — die müssen erkannt werden."""
    assert trg("remote_button_short_release")
    assert trg("remote_button_long_press")
    assert trg("remote_button_long_release")


def test_shelly_eingaenge():
    for kind in ("single_push", "double_push", "triple_push", "long_push"):
        assert trg(kind), kind


def test_bthome_taste():
    """Die Shelly-BLU-Melder und Klimasensoren haben eine echte Taste."""
    assert trg("button")


def test_druck_ist_keine_taste():
    """Der Grund für die Positivliste: „pressure" enthält „press"."""
    assert not trg("pressure")


def test_geraetetaste_von_sonos_und_miele_zaehlt_nicht():
    """Sonos und Miele melden „pressed" für ihre Gerätetaste.

    Technisch ein Taster, als Lichtschalter unsinnig — sonst stünden acht
    Lautsprecher und die Waschmaschine in der Liste der Bedienelemente.
    """
    assert not trg("pressed")


def test_zustandsmeldungen_sind_keine_tasten():
    for kind in (
        "changed_states", "turned_on", "turned_off", "playing", "paused",
        "idle", "buffering", "battery_level", "enters", "leaves",
        "motion", "no_motion", "illuminance", "temperature", "humidity",
        "opened", "failure", "autocleaning",
    ):
        assert not trg(kind), kind


def test_leerer_auslöser():
    assert not is_button_trigger({})
    assert not is_button_trigger({"type": None})


# --- Zone aus dem Namen ----------------------------------------------------

ZONEN = {
    "z1": "Flur unten",
    "z2": "Bad unten",
    "z3": "Bad oben",
    "z4": "Wohnzimmer",
    "z5": "Büro",
}


def test_zone_aus_dem_geraetenamen():
    """Zwei deiner Wandsender haben keinen Bereich zugewiesen."""
    assert zone_from_name("Wandsender Flur unten", ZONEN) == "z1"
    assert zone_from_name("Wandsender Büro", ZONEN) == "z5"


def test_laengster_treffer_gewinnt():
    """Sonst würde „Bad unten" im Zweifel im Bad oben landen."""
    assert zone_from_name("Wandsender Bad unten", ZONEN) == "z2"
    assert zone_from_name("Wandsender Bad oben", ZONEN) == "z3"


def test_leitwort_wenn_eindeutig():
    """„Wandsender Flur" gehört in die Zone „Flur unten"."""
    assert zone_from_name("Wandsender Flur", ZONEN) == "z1"


def test_mehrdeutiges_leitwort_bleibt_offen():
    """„Bad" träfe auf Bad oben und Bad unten — dann lieber keine Zone."""
    assert zone_from_name("Wandsender Bad", ZONEN) is None


def test_ohne_treffer_keine_zone():
    assert zone_from_name("Wandsender Bett Christian", ZONEN) is None
    assert zone_from_name("", ZONEN) is None


# --- Raumtypen -------------------------------------------------------------


def test_raumtypen_aus_bereichsnamen():
    assert guess_kind("Flur unten") == "verkehrsweg"
    assert guess_kind("Bad unten") == "nassbereich"
    assert guess_kind("Küche") == "kueche"
    assert guess_kind("Esszimmer") == "essraum"
    assert guess_kind("Büro") == "arbeitsraum"
    assert guess_kind("Ankleidezimmer") == "schlafraum"
    assert guess_kind("Abstellkammer") == "nebenraum"
    assert guess_kind("draußen") == "aussen"
    assert guess_kind("Wohnzimmer") == "wohnraum"


def test_unbekannter_raum_wird_wohnraum():
    assert guess_kind("Hobbyraum") == "wohnraum"


def test_jeder_raumtyp_hat_vorgaben():
    for kind in (
        "wohnraum", "verkehrsweg", "nassbereich", "kueche", "essraum",
        "arbeitsraum", "schlafraum", "nebenraum", "aussen",
    ):
        werte = KIND_DEFAULTS[kind]
        assert werte["on_below"] < werte["off_above"], kind
        assert werte["linger"] > 0, kind


def test_verkehrsweg_hat_kurzen_nachlauf():
    """Im Flur wäre ein langer Nachlauf verschwendet."""
    assert KIND_DEFAULTS["verkehrsweg"]["linger"] < KIND_DEFAULTS["wohnraum"]["linger"]


def test_arbeitsraum_hat_hoechsten_sollwert():
    """500 lx am Arbeitsplatz nach DIN EN 12464-1."""
    assert KIND_DEFAULTS["arbeitsraum"]["setpoint_lux"] == 500
    assert max(v["setpoint_lux"] for v in KIND_DEFAULTS.values()) == 500


if __name__ == "__main__":
    sys.exit(_bootstrap.run(globals()))
