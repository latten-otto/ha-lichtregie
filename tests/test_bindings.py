"""Tests der Bindungen: Bedingungen, Haltedauer, Belegungsvorlagen."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: E402

from lichtregie.core.bindings import (  # noqa: E402
    Context,
    apply_template,
    conditions_hold,
    describe,
    expiry_for,
)
from lichtregie.core.model import Binding, Circuit, Fixture, Scene, Zone  # noqa: E402


def zone() -> Zone:
    return Zone(
        id="wohnzimmer",
        name="Wohnzimmer",
        kind="wohnraum",
        linger=1200.0,
        circuits=[Circuit("k1", "Spots", "general", [Fixture("light.a", "Spots")])],
        scenes=[
            Scene(id="ankommen", name="Ankommen"),
            Scene(id="entspannen", name="Entspannen"),
            Scene(id="nachtgang", name="Nachtgang"),
        ],
    )


def binding(**kw) -> Binding:
    data = {"id": "b1", "scene_id": "ankommen"}
    data.update(kw)
    return Binding(**data)


# --- Bedingungen -----------------------------------------------------------


def test_no_conditions_always_holds():
    ok, why = conditions_hold(binding(), Context())
    assert ok and "erfüllt" in why


def test_max_lux_blocks_in_bright_room():
    b = binding(conditions={"max_lux": 200})
    assert conditions_hold(b, Context(lux=340))[0] is False
    assert conditions_hold(b, Context(lux=120))[0] is True
    # Ohne Messwert wird nicht blockiert — sonst bliebe es dunkel.
    assert conditions_hold(b, Context(lux=None))[0] is True


def test_min_lux_for_outdoor_use():
    b = binding(conditions={"min_lux": 500})
    assert conditions_hold(b, Context(lux=800))[0] is True
    assert conditions_hold(b, Context(lux=100))[0] is False


def test_night_only():
    b = binding(conditions={"nur_nachts": True})
    assert conditions_hold(b, Context(night=True))[0] is True
    assert conditions_hold(b, Context(night=False))[0] is False


def test_day_only():
    b = binding(conditions={"nur_nachts": False})
    assert conditions_hold(b, Context(night=False))[0] is True
    assert conditions_hold(b, Context(night=True))[0] is False


def test_mode_condition():
    b = binding(conditions={"betriebsart": "gaeste"})
    assert conditions_hold(b, Context(mode="gaeste"))[0] is True
    assert conditions_hold(b, Context(mode="normal"))[0] is False


def test_state_threshold():
    """„Erst wenn jemand sitzt" — nicht beim Durchgehen."""
    b = binding(conditions={"ab_zustand": "vertieft"})
    assert conditions_hold(b, Context(state="vertieft"))[0] is True
    assert conditions_hold(b, Context(state="belegt"))[0] is False


def test_time_window():
    b = binding(conditions={"zeitfenster": {"von": "06:00", "bis": "09:00"}})
    assert conditions_hold(b, Context(minute_of_day=7 * 60))[0] is True
    assert conditions_hold(b, Context(minute_of_day=14 * 60))[0] is False


def test_time_window_over_midnight():
    b = binding(conditions={"zeitfenster": {"von": "22:00", "bis": "05:00"}})
    assert conditions_hold(b, Context(minute_of_day=23 * 60))[0] is True
    assert conditions_hold(b, Context(minute_of_day=3 * 60))[0] is True
    assert conditions_hold(b, Context(minute_of_day=12 * 60))[0] is False


def test_weekdays():
    b = binding(conditions={"wochentage": [0, 1, 2, 3, 4]})
    assert conditions_hold(b, Context(weekday=2))[0] is True
    assert conditions_hold(b, Context(weekday=6))[0] is False


def test_only_when_empty():
    b = binding(conditions={"nur_wenn_leer": True})
    assert conditions_hold(b, Context(occupied=False))[0] is True
    assert conditions_hold(b, Context(occupied=True))[0] is False


def test_reason_is_useful():
    b = binding(conditions={"max_lux": 200})
    ok, why = conditions_hold(b, Context(lux=340))
    assert not ok
    assert "340" in why and "200" in why


# --- Haltedauer ------------------------------------------------------------


def test_hold_while_occupied_uses_linger():
    b = binding(hold="solange_belegt")
    assert expiry_for(b, zone(), Context(now=1000.0)) == 1000.0 + 1200.0


def test_hold_fixed():
    b = binding(hold="feste_dauer", hold_seconds=2700.0)
    assert expiry_for(b, zone(), Context(now=0.0)) == 2700.0


def test_holds_without_expiry():
    for mode in ("bis_leer", "bis_gegendruck", "bis_andere_szene", "unbegrenzt"):
        assert expiry_for(binding(hold=mode), zone(), Context()) is None


def test_hold_until_time():
    b = binding(hold="bis_zeitpunkt", until="23:00")
    # 21:00 Uhr, also noch zwei Stunden
    expiry = expiry_for(b, zone(), Context(now=0.0, minute_of_day=21 * 60))
    assert expiry == 2 * 3600.0


def test_hold_until_time_over_midnight():
    b = binding(hold="bis_zeitpunkt", until="06:00")
    expiry = expiry_for(b, zone(), Context(now=0.0, minute_of_day=23 * 60))
    assert expiry == 7 * 3600.0


# --- Vorlagen --------------------------------------------------------------


def test_template_classic():
    out = apply_template("klassisch", ["1", "2"], ["ankommen", "putzen"])
    keys = {(b.trigger["taste"], b.trigger["geste"], b.action) for b in out}
    assert ("1", "tippen", "scene") in keys
    assert ("1", "doppelt", "scene") in keys
    assert ("2", "tippen", "zone_aus") in keys
    assert ("2", "lang", "etage_aus") in keys


def test_template_cycle_matches_todays_switch():
    """Das Durchtipp-Muster, das heute der Modus-Umschalter macht."""
    out = apply_template("durchtippen", ["1", "2"], ["a", "b", "c"])
    actions = [b.action for b in out]
    assert "weiter" in actions and "automatik" in actions and "zone_aus" in actions


def test_template_direct_assigns_one_scene_per_button():
    out = apply_template("direktwahl", ["1", "2", "3", "4"], ["a", "b", "c"])
    scene_bindings = [b for b in out if b.action == "scene"]
    assert [b.scene_id for b in scene_bindings] == ["a", "b", "c"]
    assert out[-1].action == "etage_aus"


def test_template_day_night_splits_one_button():
    out = apply_template("tagnacht", ["1", "2"], ["ankommen", "nachtgang"])
    day = [b for b in out if b.conditions.get("nur_nachts") is False]
    night = [b for b in out if b.conditions.get("nur_nachts") is True]
    assert len(day) == 1 and len(night) == 1
    assert day[0].trigger["taste"] == night[0].trigger["taste"]
    assert night[0].scene_id == "nachtgang"
    assert day[0].id != night[0].id


def test_unknown_template_is_empty():
    assert apply_template("gibtsnicht", ["1"], ["a"]) == []


def test_template_survives_single_button_remote():
    out = apply_template("klassisch", ["1"], ["ankommen"])
    assert out and all(b.trigger["taste"] == "1" for b in out)


# --- Klartext --------------------------------------------------------------


def test_describe_reads_like_a_sentence():
    z = zone()
    text = describe(binding(hold="feste_dauer", hold_seconds=2700, layer=50), z)
    assert "Ankommen" in text and "45 min" in text and "Ebene 50" in text
    assert "Zone aus" in describe(binding(action="zone_aus"), z)


if __name__ == "__main__":
    sys.exit(_bootstrap.run(globals()))
