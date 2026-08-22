"""Tests der Gestennormalisierung — mit echten Rohereignissen der Anlage."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: E402

from lichtregie.link.gestures import (  # noqa: E402
    GestureRecognizer,
    describe_source,
)

TAP, DOUBLE, TRIPLE = "tippen", "doppelt", "dreifach"
HOLD, RELEASE, LONG = "halten", "loslassen", "lang"


def gestures(events):
    return [e.gesture for e in events]


# --- Busch-Jaeger RB01 über deCONZ ----------------------------------------
# Meldet nur short_release, long_press, long_release.


def test_busch_jaeger_single_tap():
    r = GestureRecognizer()
    assert r.feed("ws1", "button_3", "remote_button_short_release", 0.0) == []
    assert r.waiting
    assert gestures(r.due("ws1", 0.2)) == []  # Fenster läuft noch
    assert gestures(r.due("ws1", 0.5)) == [TAP]
    assert not r.waiting


def test_busch_jaeger_double_tap_is_synthesized():
    """Das Gerät kennt keinen Doppelklick — die Software bildet ihn."""
    r = GestureRecognizer()
    r.feed("ws1", "button_1", "remote_button_short_release", 0.0)
    r.feed("ws1", "button_1", "remote_button_short_release", 0.15)
    assert gestures(r.due("ws1", 0.5)) == [DOUBLE]


def test_busch_jaeger_triple_tap():
    r = GestureRecognizer()
    for t in (0.0, 0.12, 0.24):
        r.feed("ws1", "button_1", "remote_button_short_release", t)
    assert gestures(r.due("ws1", 0.5)) == [TRIPLE]


def test_taps_outside_window_stay_separate():
    r = GestureRecognizer()
    r.feed("ws1", "button_1", "remote_button_short_release", 0.0)
    first = r.due("ws1", 0.45)
    r.feed("ws1", "button_1", "remote_button_short_release", 0.5)
    second = r.due("ws1", 1.0)
    assert gestures(first) == [TAP]
    assert gestures(second) == [TAP]


def test_busch_jaeger_hold_and_release():
    """Dimmen: langer Druck startet, Loslassen beendet."""
    r = GestureRecognizer()
    down = r.feed("ws1", "button_2", "remote_button_long_press", 0.0)
    up = r.feed("ws1", "button_2", "remote_button_long_release", 1.8)
    assert gestures(down) == [HOLD]
    assert gestures(up) == [RELEASE]


def test_release_without_hold_is_ignored():
    """Ein Loslassen ohne vorheriges Halten erzeugt keine Geste."""
    r = GestureRecognizer()
    assert r.feed("ws1", "button_2", "remote_button_long_release", 1.0) == []


def test_hold_cancels_pending_tap():
    """Wer gedrückt hält, wollte kein Tippen."""
    r = GestureRecognizer()
    r.feed("ws1", "button_1", "remote_button_short_release", 0.0)
    r.feed("ws1", "button_1", "remote_button_long_press", 0.1)
    assert gestures(r.due("ws1", 1.0)) == []


# --- Shelly-Eingang als Ereignis-Entität ----------------------------------


def test_shelly_direct_gestures():
    """Shelly meldet Doppel und Dreifach selbst — nicht noch einmal bilden."""
    r = GestureRecognizer()
    assert gestures(r.feed("in0", "1", "double_push", 0.0)) == [DOUBLE]
    assert gestures(r.feed("in0", "1", "triple_push", 1.0)) == [TRIPLE]
    assert gestures(r.feed("in0", "1", "long_push", 2.0)) == [LONG]


def test_shelly_single_push_still_waits():
    """Auch ein gemeldeter Einzeltipper wartet, falls ein zweiter folgt."""
    r = GestureRecognizer()
    assert r.feed("in0", "1", "single_push", 0.0) == []
    assert gestures(r.due("in0", 0.5)) == [TAP]


# --- Shelly i4: nur binäre Flanken ----------------------------------------


def test_binary_short_press_becomes_tap():
    r = GestureRecognizer()
    r.feed_binary("i4", "0", closed=True, now=0.0)
    assert r.feed_binary("i4", "0", closed=False, now=0.2) == []
    assert gestures(r.due("i4", 0.7)) == [TAP]


def test_binary_long_press_becomes_long():
    r = GestureRecognizer()
    r.feed_binary("i4", "0", closed=True, now=0.0)
    out = r.feed_binary("i4", "0", closed=False, now=0.9)
    assert gestures(out) == [LONG]


def test_binary_held_starts_hold_then_release():
    """Halten muss beginnen, während der Kontakt noch zu ist — sonst dimmt nichts."""
    r = GestureRecognizer()
    r.feed_binary("i4", "0", closed=True, now=0.0)
    assert gestures(r.due("i4", 0.3)) == []
    assert gestures(r.due("i4", 0.7)) == [HOLD]
    assert gestures(r.due("i4", 1.5)) == []  # nicht doppelt melden
    out = r.feed_binary("i4", "0", closed=False, now=2.0)
    assert gestures(out) == [RELEASE]


def test_binary_open_without_close_is_ignored():
    r = GestureRecognizer()
    assert r.feed_binary("i4", "0", closed=False, now=1.0) == []


# --- IKEA: nur initial_press ----------------------------------------------


def test_ikea_initial_press_is_tap():
    r = GestureRecognizer()
    r.feed("tradfri", "1", "initial_press", 0.0)
    assert gestures(r.due("tradfri", 0.5)) == [TAP]


# --- Unbekanntes Fabrikat -------------------------------------------------


def test_unknown_event_is_not_dropped():
    """Exotisches bleibt bedienbar, statt verworfen zu werden."""
    r = GestureRecognizer()
    r.feed("fremd", "1", "irgendwas_neues", 0.0)
    assert gestures(r.due("fremd", 0.5)) == [TAP]


# --- Zerlegung der Rohformate ---------------------------------------------


def test_describe_device_trigger():
    button, action = describe_source(
        {"type": "remote_button_short_release", "subtype": "button_3"}
    )
    assert (button, action) == ("button_3", "remote_button_short_release")


def test_describe_deconz_numeric_codes():
    """Der Zahlencode aus deconz_event: Tausenderstelle ist die Taste."""
    assert describe_source({"event": 1002}) == ("1", "short_release")
    assert describe_source({"event": 3001}) == ("3", "long_press")
    assert describe_source({"event": 4003}) == ("4", "long_release")
    assert describe_source({"event": 2000}) == ("2", "initial_press")


def test_describe_event_entity():
    assert describe_source({"event_type": "double_push", "button": "2"}) == (
        "2",
        "double_push",
    )


# --- Mehrere Tasten gleichzeitig ------------------------------------------


def test_buttons_are_independent():
    r = GestureRecognizer()
    r.feed("ws1", "button_1", "remote_button_short_release", 0.0)
    r.feed("ws1", "button_2", "remote_button_short_release", 0.05)
    r.feed("ws1", "button_2", "remote_button_short_release", 0.10)
    out = {e.button: e.gesture for e in r.due("ws1", 0.6)}
    assert out == {"button_1": TAP, "button_2": DOUBLE}


if __name__ == "__main__":
    sys.exit(_bootstrap.run(globals()))
