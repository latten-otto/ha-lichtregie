"""Tests des Tagesverlaufs und der Konstantlichtregelung."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: E402

from lichtregie.core.control import (  # noqa: E402
    Calibration,
    ConstantLight,
    calibration_from_run,
    own_lux,
)
from lichtregie.core.daylight import (  # noqa: E402
    DEFAULT_CURVES,
    Anchor,
    DaylightCurve,
    Point,
)

TZ = timezone(timedelta(hours=2))
DAY = datetime(2026, 6, 21, tzinfo=TZ).date()
SUNRISE = datetime(2026, 6, 21, 4, 50, tzinfo=TZ)
SUNSET = datetime(2026, 6, 21, 21, 55, tzinfo=TZ)
# Winterlicher Vergleichstag
W_SUNRISE = datetime(2026, 12, 21, 8, 35, tzinfo=TZ)
W_SUNSET = datetime(2026, 12, 21, 15, 55, tzinfo=TZ)


def at(hour: int, minute: int = 0, month: int = 6, day: int = 21):
    return datetime(2026, month, day, hour, minute, tzinfo=TZ)


# --- Tagesverlauf ----------------------------------------------------------


def test_night_is_warm_and_dim():
    curve = DEFAULT_CURVES["wohnen"]
    kelvin, factor = curve.at_time(at(2, 0), SUNRISE, SUNSET)
    assert kelvin <= 2500, kelvin
    assert factor <= 0.30, factor


def test_noon_is_cool_and_bright():
    curve = DEFAULT_CURVES["wohnen"]
    kelvin, factor = curve.at_time(at(13, 20), SUNRISE, SUNSET)
    assert kelvin >= 5000, kelvin
    assert factor >= 0.95, factor


def test_evening_is_warmer_than_afternoon():
    curve = DEFAULT_CURVES["wohnen"]
    afternoon, _ = curve.at_time(at(16, 0), SUNRISE, SUNSET)
    evening, _ = curve.at_time(at(22, 30), SUNRISE, SUNSET)
    assert evening < afternoon


def test_curve_follows_the_sun_not_the_clock():
    """Im Dezember beginnt die Absenkung früher — das ist der ganze Zweck."""
    curve = DEFAULT_CURVES["wohnen"]
    summer, _ = curve.at_time(at(20, 0), SUNRISE, SUNSET)
    winter, _ = curve.at_time(at(20, 0, month=12), W_SUNRISE, W_SUNSET)
    assert winter < summer, (winter, summer)


def test_curve_is_continuous_over_midnight():
    """Kein Sprung zwischen 23:59 und 00:01."""
    curve = DEFAULT_CURVES["wohnen"]
    before, factor_before = curve.at_time(at(23, 59), SUNRISE, SUNSET)
    after, factor_after = curve.at_time(at(0, 1), SUNRISE, SUNSET)
    assert abs(before - after) < 120, (before, after)
    assert abs(factor_before - factor_after) < 0.06


def test_all_default_curves_stay_in_range():
    for key, curve in DEFAULT_CURVES.items():
        for minute in range(0, 1440, 20):
            kelvin, factor = curve.at_time(
                at(minute // 60, minute % 60), SUNRISE, SUNSET
            )
            assert 1800 <= kelvin <= 6600, (key, minute, kelvin)
            assert 0.0 <= factor <= 1.0, (key, minute, factor)


def test_sample_covers_the_day():
    points = DEFAULT_CURVES["wohnen"].sample(DAY, SUNRISE, SUNSET, steps=48)
    assert len(points) == 49
    assert points[0]["minute"] == 0
    assert points[-1]["minute"] == 1440


def test_single_point_curve_is_constant():
    curve = DaylightCurve("x", "X", [Point(Anchor.CLOCK, 3000, 0.5, at="12:00")])
    assert curve.at_time(at(3, 0), SUNRISE, SUNSET) == (3000, 0.5)


def test_offset_shifts_the_point():
    curve = DaylightCurve(
        "x",
        "X",
        [
            Point(Anchor.SUNSET, 4000, 1.0, offset=-120),
            Point(Anchor.SUNSET, 2200, 0.2),
        ],
    )
    early, _ = curve.at_time(SUNSET - timedelta(minutes=120), SUNRISE, SUNSET)
    late, _ = curve.at_time(SUNSET, SUNRISE, SUNSET)
    assert early == 4000 and late == 2200


def test_curve_roundtrip_through_dict():
    curve = DEFAULT_CURVES["arbeiten"]
    again = DaylightCurve.from_dict(curve.to_dict())
    assert again.at_time(at(12, 0), SUNRISE, SUNSET) == curve.at_time(
        at(12, 0), SUNRISE, SUNSET
    )


# --- Eigenanteil -----------------------------------------------------------


def test_own_lux_sums_contributions():
    cal = Calibration(contributions={"k1": 200.0, "k2": 90.0}, dark=4.0, valid=True)
    assert own_lux(cal, {"k1": 1.0, "k2": 1.0}) == 294.0
    assert own_lux(cal, {"k1": 0.5, "k2": 0.0}) == 104.0


def test_own_lux_uses_the_dimming_curve():
    """Halber Sollwert ist bei logarithmischer Kurve nicht halbes Licht."""
    cal = Calibration(contributions={"k1": 200.0}, dark=0.0, valid=True)
    naive = own_lux(cal, {"k1": 0.5})
    real = own_lux(cal, {"k1": 0.5}, curves={"k1": ("log", 0.01, 1.0)})
    assert naive == 100.0
    assert 15 < real < 25, real


def test_calibration_drops_noise():
    """Beiträge unter einem Lux sind Rauschen, kein Messwert."""
    cal = calibration_from_run(dark=5.0, readings={"k1": 205.0, "k2": 5.4})
    assert cal.contributions == {"k1": 200.0}
    assert cal.valid is True


def test_calibration_without_result_is_invalid():
    cal = calibration_from_run(dark=5.0, readings={"k1": 5.2})
    assert cal.valid is False


# --- Regler ----------------------------------------------------------------


def test_deadband_keeps_it_quiet():
    reg = ConstantLight(setpoint=300.0)
    target, why = reg.step(measured=290.0, own=100.0, current=0.5, dt=10.0)
    assert target is None
    assert "Totband" in why


def test_regulator_raises_when_too_dark():
    reg = ConstantLight(setpoint=300.0)
    target, _ = reg.step(measured=150.0, own=100.0, current=0.5, dt=10.0)
    assert target is not None and target > 0.5


def test_regulator_lowers_when_too_bright():
    reg = ConstantLight(setpoint=300.0)
    target, _ = reg.step(measured=460.0, own=200.0, current=0.8, dt=10.0)
    assert target is not None and target < 0.8


def test_rate_limit_keeps_changes_invisible():
    """Mehr als ein Prozent pro Sekunde darf nicht herauskommen."""
    reg = ConstantLight(setpoint=500.0)
    target, _ = reg.step(measured=10.0, own=0.0, current=0.2, dt=10.0)
    assert target is not None
    assert target - 0.2 <= 0.10 + 1e-9, target


def test_daylight_releases_the_zone():
    """Reicht das Tageslicht, wird sauber abgeschaltet statt zu kriechen."""
    reg = ConstantLight(setpoint=300.0, floor=0.05)
    target, why = reg.step(measured=520.0, own=20.0, current=0.4, dt=10.0)
    assert target == 0.05
    assert "Tageslicht" in why


def test_settle_time_blocks_the_loop():
    """Direkt nach einem Stellbefehl ist der Messwert nicht zu gebrauchen."""
    reg = ConstantLight(setpoint=300.0)
    reg.disturb(now=100.0)
    target, why = reg.step(measured=10.0, own=0.0, current=0.5, dt=10.0, now=101.0)
    assert target is None and "beruhigt" in why
    target, _ = reg.step(measured=10.0, own=0.0, current=0.5, dt=10.0, now=115.0)
    assert target is not None


def test_regulator_converges():
    """Über mehrere Schritte nähert sich die Zone dem Sollwert."""
    reg = ConstantLight(setpoint=300.0, max_rate=0.05)
    cal = Calibration(contributions={"k1": 600.0}, dark=0.0, valid=True)
    level = 0.05
    daylight = 60.0
    for _ in range(200):
        measured = daylight + own_lux(cal, {"k1": level}, {"k1": ("linear", 0.0, 1.0)})
        target, _ = reg.step(measured, measured - daylight, level, dt=10.0)
        if target is not None:
            level = target
    final = daylight + own_lux(cal, {"k1": level}, {"k1": ("linear", 0.0, 1.0)})
    assert abs(final - 300.0) <= reg.deadband + 5, final


def test_regulator_stays_within_limits():
    reg = ConstantLight(setpoint=900.0, floor=0.1, ceiling=0.8, max_rate=1.0)
    level = 0.5
    for _ in range(50):
        target, _ = reg.step(measured=50.0, own=10.0, current=level, dt=10.0)
        if target is not None:
            level = target
    assert 0.1 <= level <= 0.8


if __name__ == "__main__":
    sys.exit(_bootstrap.run(globals()))
