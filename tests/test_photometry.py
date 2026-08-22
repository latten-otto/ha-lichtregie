"""Tests der lichttechnischen Rechnungen — laufen ohne Home Assistant."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: E402

from lichtregie.core import photometry as p  # noqa: E402

LOG = "log"
GAMMA = "gamma"
LINEAR = "linear"
DALI = "dali"
ALL_CURVES = (LOG, GAMMA, LINEAR, DALI)


def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


# --- normative DALI-Kurve --------------------------------------------------


def test_dali_matches_standard():
    """Stufe 1 sind 0,1 %, Stufe 254 sind 100 % Lichtstrom."""
    assert p.dali_flux(0.0) == 0.0
    assert approx(p.dali_flux(1.0), 1.0, 1e-9)
    assert approx(p.dali_flux(1e-12), 0.001, 1e-6)
    # halber Regelweg entspricht gut 3 % Lichtstrom
    assert 0.030 < p.dali_flux(0.5) < 0.033


# --- Kurven allgemein ------------------------------------------------------


def test_curves_hit_the_limits():
    """Voller Sollwert erreicht die Obergrenze, kleinster die Untergrenze."""
    for curve in ALL_CURVES:
        top = p.level_to_flux(1.0, curve, 0.01, 0.80)
        assert approx(top, 0.80, 1e-6), (curve, top)
        bottom = p.level_to_flux(1e-9, curve, 0.01, 0.80)
        assert approx(bottom, 0.01, 1e-3), (curve, bottom)


def test_curves_monotonic():
    """Mehr Sollwert ergibt nie weniger Licht."""
    for curve in ALL_CURVES:
        values = [p.level_to_flux(i / 50, curve, 0.01, 1.0) for i in range(51)]
        assert all(b >= a for a, b in zip(values, values[1:])), curve


def test_curve_roundtrip():
    """Hin- und Rückrechnung trifft sich wieder."""
    for curve in ALL_CURVES:
        for level in (0.05, 0.2, 0.5, 0.75, 1.0):
            flux = p.level_to_flux(level, curve, 0.01, 0.9)
            back = p.flux_to_level(flux, curve, 0.01, 0.9)
            assert approx(back, level, 1e-6), (curve, level, back)


def test_log_curve_is_geometric():
    """Die Standardkurve verteilt gleiche Sollwertschritte auf gleiche Faktoren."""
    lo, hi = 0.01, 1.0
    a = p.level_to_flux(0.0001, LOG, lo, hi)
    b = p.level_to_flux(0.5, LOG, lo, hi)
    c = p.level_to_flux(1.0, LOG, lo, hi)
    assert approx(a, 0.01, 1e-4)
    assert approx(b, 0.1, 1e-3)  # geometrische Mitte zwischen 1 % und 100 %
    assert approx(c, 1.0, 1e-6)


# --- Stellwerte ------------------------------------------------------------


def test_brightness_never_zero_when_on():
    """Ein eingeschalteter Kreis bekommt nie den Stellwert 0."""
    for level in (0.001, 0.01, 0.1, 1.0):
        assert p.level_to_brightness(level, LOG, 0.01, 1.0) >= 1
    assert p.level_to_brightness(0.0) == 0


def test_brightness_respects_ceiling():
    """Sollwert 100 % bedeutet 100 % der Betriebsgrenze, nicht der Leuchte."""
    assert p.level_to_brightness(1.0, LOG, 0.01, 0.80) == round(0.80 * 255)


def test_brightness_roundtrip():
    """Aus einem gemeldeten Stellwert wird der Sollwert zurückgewonnen."""
    for level in (0.1, 0.35, 0.7, 1.0):
        b = p.level_to_brightness(level, LOG, 0.01, 1.0)
        back = p.brightness_to_level(b, LOG, 0.01, 1.0)
        assert abs(back - level) < 0.05, (level, b, back)


def test_log_beats_dali_on_eight_bit():
    """Der Grund für die Voreinstellung: nutzbare Stufen bei 8 Bit.

    Die normative DALI-Kurve verschenkt bei 8-Bit-Stellwerten den unteren
    Regelweg, weil 0,1 % Lichtstrom unter der kleinsten darstellbaren Stufe
    von 0,39 % liegt. Gemessen: DALI 92 unterscheidbare Stufen, die
    logarithmische Kurve über den Regelbereich 118 bei 1 % Minimalwert und
    135 bei 3 %.
    """
    dali_steps = p.usable_steps(DALI, 0.0, 1.0)
    log_steps = p.usable_steps(LOG, 0.01, 1.0)
    assert dali_steps == 92, dali_steps
    assert log_steps > dali_steps, (log_steps, dali_steps)
    assert p.usable_steps(LOG, 0.03, 1.0) > log_steps


def test_log_curve_matches_perception():
    """Halber Regelweg liegt im Fenster der Stevens-Potenzfunktion.

    Empfundene Helligkeit wächst etwa mit der dritten Wurzel des
    Lichtstroms. Halbe empfundene Helligkeit entspricht damit rund 12 %
    Lichtstrom. Die logarithmische Kurve trifft das; Gamma 2,2 bleibt mit
    22 % deutlich zu hell.
    """
    mid_log = p.level_to_flux(0.5, LOG, 0.01, 1.0)
    mid_gamma = p.level_to_flux(0.5, GAMMA, 0.01, 1.0)
    assert 0.08 <= mid_log <= 0.14, mid_log
    assert mid_gamma > 0.20, mid_gamma


def test_usable_steps_warns_on_narrow_range():
    """Eine zu enge Betriebsgrenze liefert wenige unterscheidbare Stufen."""
    assert p.usable_steps(LOG, 0.50, 0.55) < 30


# --- Farbtemperatur --------------------------------------------------------


def test_mired_roundtrip():
    for k in (2200, 2700, 4000, 6500):
        assert approx(p.mired_to_kelvin(p.kelvin_to_mired(k)), k, 1e-6)


def test_blend_is_mired_linear():
    """Die Mitte eines Übergangs liegt in Mired, nicht in Kelvin."""
    assert approx(p.blend_kelvin(2000, 6000, 0.5), 3000.0, 1e-6)
    assert approx(p.blend_kelvin(2000, 6000, 0.0), 2000.0)
    assert approx(p.blend_kelvin(2000, 6000, 1.0), 6000.0)


def test_fit_kelvin():
    assert p.fit_kelvin(1800, 2200, 6500) == 2200
    assert p.fit_kelvin(9000, 2200, 6500) == 6500
    assert p.fit_kelvin(3000, 2200, 6500) == 3000
    assert p.fit_kelvin(3000, None, None) == 3000


def test_kelvin_to_xy_known_points():
    """Bekannte Weißpunkte auf dem Planck-Ort."""
    x65, y65 = p.kelvin_to_xy(6500)
    assert abs(x65 - 0.3135) < 0.005 and abs(y65 - 0.3237) < 0.005
    x27, y27 = p.kelvin_to_xy(2700)
    assert abs(x27 - 0.4599) < 0.006 and abs(y27 - 0.4106) < 0.006


def test_kelvin_to_xy_monotonic():
    """Wärmer heißt weiter rechts auf der Kurve."""
    xs = [p.kelvin_to_xy(k)[0] for k in range(2000, 6600, 200)]
    assert all(b <= a for a, b in zip(xs, xs[1:]))


if __name__ == "__main__":
    sys.exit(_bootstrap.run(globals()))
