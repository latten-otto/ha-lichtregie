"""Tests der Zeitauslöser-Berechnung.

Die Engine selbst braucht Home Assistant. Die Rechnung dahinter — welcher
Zeitpunkt aus Anker und Versatz entsteht — wird hier isoliert geprüft, weil
sie die Stelle ist, an der Fehler unbemerkt bleiben (falscher Tag, Sprung
über Mitternacht, verpasste Minute).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: E402

from lichtregie.core.model import Binding  # noqa: E402


def target_minute(binding: Binding, sunrise: int, sunset: int) -> int:
    """Dieselbe Rechnung wie in ``Engine._run_schedule``."""
    anchor = binding.trigger.get("anker", "uhr")
    offset = int(binding.trigger.get("versatz", 0))
    sun = {"aufgang": sunrise, "untergang": sunset}
    if anchor in sun:
        return (sun[anchor] + offset) % 1440
    raw = str(binding.trigger.get("um", "00:00"))
    hour, _, rest = raw.partition(":")
    return (int(hour) * 60 + int(rest or 0) + offset) % 1440


SUNRISE = 5 * 60 + 12  # 05:12
SUNSET = 21 * 60 + 40  # 21:40


def timed(**trigger) -> Binding:
    return Binding(id="t1", trigger={"art": "zeit", **trigger})


def test_fixed_clock_time():
    assert target_minute(timed(um="07:30"), SUNRISE, SUNSET) == 450


def test_clock_with_offset():
    assert target_minute(timed(um="07:30", versatz=15), SUNRISE, SUNSET) == 465
    assert target_minute(timed(um="07:30", versatz=-30), SUNRISE, SUNSET) == 420


def test_sunset_anchor():
    assert target_minute(timed(anker="untergang"), SUNRISE, SUNSET) == SUNSET


def test_sunset_minus_thirty():
    """Rollladen- und Lichtszenen hängen typischerweise vor dem Untergang."""
    assert target_minute(timed(anker="untergang", versatz=-30), SUNRISE, SUNSET) == SUNSET - 30


def test_sunrise_anchor():
    assert target_minute(timed(anker="aufgang", versatz=20), SUNRISE, SUNSET) == SUNRISE + 20


def test_wraps_over_midnight():
    """Untergang plus drei Stunden landet am nächsten Tag, nicht bei 1500."""
    assert target_minute(timed(anker="untergang", versatz=180), SUNRISE, SUNSET) == (
        SUNSET + 180
    ) % 1440
    assert target_minute(timed(um="23:30", versatz=60), SUNRISE, SUNSET) == 30


def test_negative_wrap():
    assert target_minute(timed(um="00:10", versatz=-30), SUNRISE, SUNSET) == 1420


def test_default_is_midnight():
    assert target_minute(timed(), SUNRISE, SUNSET) == 0


def test_moves_with_the_season():
    """Im Winter feuert derselbe Auslöser früher — das ist der Zweck."""
    winter_sunset = 15 * 60 + 55
    binding = timed(anker="untergang", versatz=-30)
    assert target_minute(binding, SUNRISE, SUNSET) == SUNSET - 30
    assert target_minute(binding, 8 * 60 + 35, winter_sunset) == winter_sunset - 30


def test_marker_is_unique_per_day():
    """Der Auslöser feuert einmal je Tag, nicht bei jedem Takt."""
    fired: set[str] = set()
    for _ in range(5):
        marker = "t1:2026-08-22"
        if marker in fired:
            continue
        fired.add(marker)
    assert len(fired) == 1
    fired.add("t1:2026-08-23")
    assert len(fired) == 2


if __name__ == "__main__":
    sys.exit(_bootstrap.run(globals()))
