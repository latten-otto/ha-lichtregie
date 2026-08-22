"""Lichttechnische Rechnungen.

Reine Funktionen ohne Home-Assistant-Bezug, damit sie eigenständig testbar sind.

Begriffe
--------
Sollwert (``level``)
    Was der Bediener einstellt: empfundene Helligkeit, 0.0 bis 1.0.
Lichtstrom (``flux``)
    Was die Leuchte tatsächlich abgibt, 0.0 bis 1.0 der Nennleistung.
Stellwert (``brightness``)
    Was Home Assistant entgegennimmt, 1 bis 255.

Zur Wahl der Kurve
------------------
DALI verteilt seine 254 Stufen logarithmisch über drei Dekaden, von 0,1 %
bis 100 % Lichtstrom (IEC 62386-102). Diese Kurve unverändert auf den
8-Bit-Stellwert von Home Assistant abzubilden funktioniert nicht: 0,1 %
Lichtstrom liegt weit unter der kleinsten darstellbaren Stufe von 1/255,
also 0,39 %. Der gesamte untere Drittel des Regelwegs fiele auf denselben
Stellwert zusammen.

Deshalb ist die Voreinstellung ``CURVE_LOG``: dieselbe logarithmische
Charakteristik, aber gespannt über den *tatsächlich nutzbaren* Bereich der
Leuchte zwischen ``min_flux`` und ``max_flux``. Bei einer Leuchte, die ab
1 % stabil brennt, ergibt Sollwert 0 → 1 %, 0,5 → 10 %, 1,0 → 100 %.
Das ist die gleiche Wahrnehmungsgleichmäßigkeit ohne unerreichbaren
Regelweg.
"""

from __future__ import annotations

import math

from ..const import (
    CURVE_DALI,
    CURVE_GAMMA,
    CURVE_LINEAR,
    CURVE_LOG,
    DEFAULT_GAMMA,
    FLOOR_FLUX,
)

__all__ = [
    "clamp",
    "level_to_flux",
    "flux_to_level",
    "level_to_brightness",
    "brightness_to_level",
    "usable_steps",
    "dali_flux",
    "kelvin_to_mired",
    "mired_to_kelvin",
    "blend_kelvin",
    "kelvin_to_xy",
    "fit_kelvin",
]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Begrenzt einen Wert auf einen Bereich."""
    return low if value < low else high if value > high else value


# --------------------------------------------------------------------------
# Dimmkurven
# --------------------------------------------------------------------------


def dali_flux(level: float) -> float:
    """Normative DALI-Kurve nach IEC 62386-102, 0,1 % bis 100 %.

    Wird für den Vergleich und für Geräte mit echtem DALI-Vorschaltgerät
    gebraucht, nicht als Voreinstellung für Funkleuchten.
    """
    if level <= 0.0:
        return 0.0
    step = 1.0 + clamp(level) * 253.0
    return 10.0 ** (3.0 * (step - 1.0) / 253.0 - 1.0) / 100.0


def _limits(min_flux: float, max_flux: float) -> tuple[float, float]:
    """Betriebsgrenzen prüfen und in eine brauchbare Form bringen."""
    lo = clamp(min_flux, 0.0, 1.0)
    hi = clamp(max_flux, 0.0, 1.0)
    if hi <= lo:
        hi = min(1.0, lo + 1e-6)
    return lo, hi


def level_to_flux(
    level: float,
    curve: str = CURVE_LOG,
    min_flux: float = 0.0,
    max_flux: float = 1.0,
) -> float:
    """Sollwert in Lichtstromanteil umrechnen.

    Der Rückgabewert liegt immer zwischen ``min_flux`` und ``max_flux``.
    Ein Sollwert von 0 bedeutet aus und wird vom Aufrufer behandelt.
    """
    level = clamp(level)
    if level <= 0.0:
        return 0.0
    lo, hi = _limits(min_flux, max_flux)

    if curve == CURVE_LINEAR:
        return lo + level * (hi - lo)
    if curve == CURVE_GAMMA:
        return lo + (level**DEFAULT_GAMMA) * (hi - lo)
    if curve == CURVE_DALI:
        return lo + dali_flux(level) * (hi - lo)

    # CURVE_LOG: geometrisch über den nutzbaren Bereich.
    base = max(lo, FLOOR_FLUX)
    return base * (hi / base) ** level


def flux_to_level(
    flux: float,
    curve: str = CURVE_LOG,
    min_flux: float = 0.0,
    max_flux: float = 1.0,
) -> float:
    """Umkehrung von :func:`level_to_flux`."""
    flux = clamp(flux)
    if flux <= 0.0:
        return 0.0
    lo, hi = _limits(min_flux, max_flux)
    span = hi - lo

    if curve == CURVE_LINEAR:
        return clamp((flux - lo) / span)
    if curve == CURVE_GAMMA:
        return clamp(((flux - lo) / span) ** (1.0 / DEFAULT_GAMMA))
    if curve == CURVE_DALI:
        share = clamp((flux - lo) / span)
        if share <= 0.0:
            return 0.0
        step = 253.0 * (math.log10(share * 100.0) + 1.0) / 3.0 + 1.0
        return clamp((step - 1.0) / 253.0)

    base = max(lo, FLOOR_FLUX)
    if flux <= base:
        return 0.0
    return clamp(math.log(flux / base) / math.log(hi / base))


def level_to_brightness(
    level: float,
    curve: str = CURVE_LOG,
    min_flux: float = 0.0,
    max_flux: float = 1.0,
) -> int:
    """Sollwert in den Stellwert 1…255 umrechnen.

    Ein eingeschalteter Kreis bekommt nie den Stellwert 0 — das Ausschalten
    entscheidet der Aufrufer, nicht die Umrechnung.
    """
    if level <= 0.0:
        return 0
    flux = level_to_flux(level, curve, min_flux, max_flux)
    return max(1, min(255, round(flux * 255.0)))


def brightness_to_level(
    brightness: int,
    curve: str = CURVE_LOG,
    min_flux: float = 0.0,
    max_flux: float = 1.0,
) -> float:
    """Stellwert zurück in den Sollwert umrechnen — für Fremdeingriffe."""
    if brightness <= 0:
        return 0.0
    return flux_to_level(brightness / 255.0, curve, min_flux, max_flux)


def usable_steps(
    curve: str = CURVE_LOG,
    min_flux: float = 0.0,
    max_flux: float = 1.0,
) -> int:
    """Wie viele unterscheidbare Stufen die Leuchte tatsächlich hergibt.

    Bei der Inbetriebnahme wird gewarnt, wenn hier weniger als etwa
    30 Stufen herauskommen — dann ist die Kurve für diese Leuchte zu steil
    oder die Betriebsgrenzen sind falsch gesetzt.
    """
    seen = {
        level_to_brightness(i / 200.0, curve, min_flux, max_flux)
        for i in range(1, 201)
    }
    return len(seen)


# --------------------------------------------------------------------------
# Farbtemperatur
# --------------------------------------------------------------------------


def kelvin_to_mired(kelvin: float) -> float:
    """Kelvin in Mired (Mikro-Reziprok-Grad)."""
    if kelvin <= 0:
        return 0.0
    return 1_000_000.0 / kelvin


def mired_to_kelvin(mired: float) -> float:
    """Mired zurück in Kelvin."""
    if mired <= 0:
        return 0.0
    return 1_000_000.0 / mired


def blend_kelvin(start: float, end: float, progress: float) -> float:
    """Farbtemperatur interpolieren — über Mired, nicht über Kelvin.

    Linear in Kelvin gerechnet rauscht ein Übergang von 2200 K auf 5000 K
    am Anfang zu schnell durch die warmen Töne. Mired entspricht der
    Wahrnehmung deutlich besser.
    """
    progress = clamp(progress)
    mired = kelvin_to_mired(start) + (
        kelvin_to_mired(end) - kelvin_to_mired(start)
    ) * progress
    return mired_to_kelvin(mired)


def fit_kelvin(
    kelvin: float, min_kelvin: float | None, max_kelvin: float | None
) -> float:
    """Zielfarbtemperatur auf den Bereich der Leuchte begrenzen."""
    if min_kelvin is not None and kelvin < min_kelvin:
        return min_kelvin
    if max_kelvin is not None and kelvin > max_kelvin:
        return max_kelvin
    return kelvin


def kelvin_to_xy(kelvin: float) -> tuple[float, float]:
    """Farbtemperatur in CIE-1931-xy auf dem Planck-Ort.

    Näherung nach Kim et al. für 1667 K bis 25000 K. Wird gebraucht, damit
    Farbleuchten dieselbe Weißtemperatur zeigen wie echte Tunable-White-
    Leuchten im selben Raum.
    """
    t = max(1667.0, min(25000.0, kelvin))

    if t <= 4000.0:
        x = -0.2661239e9 / t**3 - 0.2343589e6 / t**2 + 0.8776956e3 / t + 0.179910
    else:
        x = -3.0258469e9 / t**3 + 2.1070379e6 / t**2 + 0.2226347e3 / t + 0.240390

    if t <= 2222.0:
        y = -1.1063814 * x**3 - 1.34811020 * x**2 + 2.18555832 * x - 0.20219683
    elif t <= 4000.0:
        y = -0.9549476 * x**3 - 1.37418593 * x**2 + 2.09137015 * x - 0.16748867
    else:
        y = 3.0817580 * x**3 - 5.87338670 * x**2 + 3.75112997 * x - 0.37001483

    return round(x, 4), round(y, 4)
