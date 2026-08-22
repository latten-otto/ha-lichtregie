"""Konstantlichtregelung.

Ein geschlossener Regelkreis sieht immer beides: Tageslicht und das eigene
Kunstlicht. Ohne Trennung führt das zur Rückkopplung — das Licht regelt sich
selbst hoch oder runter. Die Trennung gelingt durch eine Kalibrierfahrt: die
Software fährt jeden Lichtkreis einzeln hoch und misst den Zuwachs am
Sensor. Danach gilt

    Fremdlicht = gemessene Lux − berechneter Eigenanteil

und ein PI-Regler führt die Kreise so nach, dass die Summe den Sollwert der
Zone trifft.

Drei Vorkehrungen halten die Regelung ruhig:

* ein Totband, damit sie bei kleinen Abweichungen gar nicht erst anfängt,
* eine Ratenbegrenzung, damit die Nachführung unter der Wahrnehmungsschwelle
  bleibt,
* eine Beruhigungszeit nach jedem Stellbefehl, bevor der Sensor wieder als
  gültig gilt.

Das Modul rechnet nur; es kennt weder Home Assistant noch Zeitgeber.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..const import MAX_TRACKING_RATE
from .photometry import clamp, level_to_flux

__all__ = ["Calibration", "ConstantLight", "own_lux"]

# Nach einem Stellbefehl braucht ein Consumer-Lux-Sensor Zeit.
SETTLE_SECONDS = 8.0
# Voreinstellung des Totbands, Anteil vom Sollwert.
DEADBAND_SHARE = 0.08


@dataclass
class Calibration:
    """Ergebnis der Kalibrierfahrt einer Zone.

    ``contributions`` hält je Lichtkreis den gemessenen Lux-Zuwachs bei
    vollem Sollwert. ``dark`` ist der Restwert bei ausgeschaltetem Licht in
    der Nacht — meist Straßenlaterne oder Standby-Leuchten.
    """

    contributions: dict[str, float] = field(default_factory=dict)
    dark: float = 0.0
    at: float = 0.0
    valid: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contributions": self.contributions,
            "dark": self.dark,
            "at": self.at,
            "valid": self.valid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Calibration:
        return cls(
            contributions={k: float(v) for k, v in (data.get("contributions") or {}).items()},
            dark=float(data.get("dark", 0.0)),
            at=float(data.get("at", 0.0)),
            valid=bool(data.get("valid", False)),
        )


def own_lux(
    calibration: Calibration,
    levels: dict[str, float],
    curves: dict[str, tuple[str, float, float]] | None = None,
) -> float:
    """Eigenanteil des Kunstlichts am Messpunkt.

    ``curves`` bildet je Lichtkreis die Dimmkurve und die Betriebsgrenzen
    ab, damit der Lichtstrom und nicht der Sollwert eingeht — bei einer
    logarithmischen Kurve ist das ein Unterschied von einer Größenordnung.
    """
    total = calibration.dark
    for circuit_id, level in levels.items():
        contribution = calibration.contributions.get(circuit_id)
        if not contribution or level <= 0:
            continue
        if curves and circuit_id in curves:
            curve, min_flux, max_flux = curves[circuit_id]
            share = level_to_flux(level, curve, min_flux, max_flux)
        else:
            share = level
        total += contribution * share
    return total


class ConstantLight:
    """PI-Regler für eine Zone."""

    def __init__(
        self,
        setpoint: float,
        deadband: float | None = None,
        kp: float = 0.0016,
        ki: float = 0.0004,
        max_rate: float = MAX_TRACKING_RATE,
        floor: float = 0.05,
        ceiling: float = 1.0,
    ) -> None:
        self.setpoint = setpoint
        self.deadband = deadband if deadband is not None else setpoint * DEADBAND_SHARE
        self.kp = kp
        self.ki = ki
        self.max_rate = max_rate
        self.floor = floor
        self.ceiling = ceiling
        self.integral = 0.0
        self.settled_at = 0.0

    # -- Zustand ------------------------------------------------------------

    def disturb(self, now: float) -> None:
        """Nach einem Stellbefehl den Sensor für eine Weile ignorieren."""
        self.settled_at = now + SETTLE_SECONDS

    def settled(self, now: float) -> bool:
        return now >= self.settled_at

    def reset(self) -> None:
        self.integral = 0.0

    # -- Regelschritt -------------------------------------------------------

    def step(
        self,
        measured: float,
        own: float,
        current: float,
        dt: float,
        now: float = 0.0,
    ) -> tuple[float | None, str]:
        """Ein Regelschritt.

        Rückgabe ist der neue Zonenfaktor und eine Begründung für das
        Protokoll. ``None`` bedeutet: nichts tun.
        """
        if not self.settled(now):
            return None, "Sensor noch nicht beruhigt"

        daylight = max(0.0, measured - own)
        error = self.setpoint - measured

        if daylight >= self.setpoint and current > self.floor:
            self.reset()
            return self.floor, f"Tageslicht reicht ({daylight:.0f} lx)"

        if abs(error) < self.deadband:
            return None, f"im Totband ({error:+.0f} lx)"

        self.integral = clamp(self.integral + error * dt, -6000.0, 6000.0)
        step = self.kp * error + self.ki * self.integral
        target = clamp(current + step, self.floor, self.ceiling)

        # Ratenbegrenzung: unterhalb dieser Änderung fällt die Nachführung
        # nicht auf.
        limit = self.max_rate * max(dt, 0.001)
        if target > current + limit:
            target = current + limit
        elif target < current - limit:
            target = current - limit

        if abs(target - current) < 0.002:
            return None, "Änderung zu klein"

        return round(target, 4), (
            f"Soll {self.setpoint:.0f} lx · gemessen {measured:.0f} lx · "
            f"Fremdlicht {daylight:.0f} lx · Faktor {current:.2f} → {target:.2f}"
        )


def calibration_from_run(
    dark: float, readings: dict[str, float], at: float = 0.0
) -> Calibration:
    """Baut das Ergebnis einer Kalibrierfahrt.

    ``readings`` sind die Messwerte mit jeweils genau einem Kreis auf
    vollem Sollwert. Beiträge unter einem Lux gelten als nicht messbar und
    werden verworfen — sonst rechnet die Regelung mit Rauschen.
    """
    contributions = {}
    for circuit_id, measured in readings.items():
        delta = measured - dark
        if delta >= 1.0:
            contributions[circuit_id] = round(delta, 2)
    return Calibration(
        contributions=contributions,
        dark=round(dark, 2),
        at=at,
        valid=bool(contributions),
    )
