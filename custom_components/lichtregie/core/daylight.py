"""Tagesverlauf — eigene Berechnung statt Fremdintegration.

Eine Kurve aus Stützpunkten liefert zu jedem Zeitpunkt eine Farbtemperatur
und einen Helligkeitsfaktor. Stützpunkte hängen wahlweise an der Uhr oder am
Sonnenstand; dadurch verschiebt sich die Absenkung im Juni von selbst nach
hinten.

Fachlicher Rahmen sind die Planungsempfehlungen für biologisch wirksame
Beleuchtung: tagsüber hoher melanopischer Anteil, abends konsequent
abgesenkt. Die Interpolation der Farbtemperatur läuft über Mired, weil das
der Wahrnehmung entspricht.

Das Modul kennt keine Zeitgeber und keine Sonnenstandsrechnung — Aufgang und
Untergang werden übergeben. Dadurch ist es vollständig testbar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from .photometry import blend_kelvin, clamp

__all__ = ["Anchor", "Point", "DaylightCurve", "DEFAULT_CURVES"]

DAY = 24 * 3600.0


class Anchor:
    """Woran ein Stützpunkt hängt."""

    CLOCK = "uhr"
    SUNRISE = "aufgang"
    SUNSET = "untergang"
    NOON = "mittag"


@dataclass
class Point:
    """Ein Stützpunkt der Kurve."""

    anchor: str
    kelvin: int
    factor: float
    at: str = "12:00"  # nur für Anchor.CLOCK
    offset: int = 0  # Minuten vor oder nach dem Anker

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchor": self.anchor,
            "kelvin": self.kelvin,
            "factor": self.factor,
            "at": self.at,
            "offset": self.offset,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Point:
        return cls(
            anchor=data.get("anchor", Anchor.CLOCK),
            kelvin=int(data.get("kelvin", 3000)),
            factor=float(data.get("factor", 1.0)),
            at=data.get("at", "12:00"),
            offset=int(data.get("offset", 0)),
        )

    def seconds(self, day: date, sunrise: datetime, sunset: datetime) -> float:
        """Zeitpunkt des Stützpunkts als Sekunden seit Mitternacht."""
        if self.anchor == Anchor.SUNRISE:
            base = sunrise
        elif self.anchor == Anchor.SUNSET:
            base = sunset
        elif self.anchor == Anchor.NOON:
            base = sunrise + (sunset - sunrise) / 2
        else:
            hour, _, minute = self.at.partition(":")
            base = datetime.combine(
                day, time(int(hour), int(minute or 0)), tzinfo=sunrise.tzinfo
            )
        moment = base + timedelta(minutes=self.offset)
        midnight = datetime.combine(day, time(0, 0), tzinfo=sunrise.tzinfo)
        return (moment - midnight).total_seconds() % DAY


class DaylightCurve:
    """Eine benannte Kurve aus Stützpunkten."""

    def __init__(self, key: str, name: str, points: list[Point]) -> None:
        self.key = key
        self.name = name
        self.points = points

    # -- Auswertung ---------------------------------------------------------

    def at_time(
        self, now: datetime, sunrise: datetime, sunset: datetime
    ) -> tuple[int, float]:
        """Farbtemperatur und Helligkeitsfaktor zu einem Zeitpunkt."""
        if not self.points:
            return 3000, 1.0

        day = now.date()
        stops = sorted(
            ((p.seconds(day, sunrise, sunset), p) for p in self.points),
            key=lambda item: item[0],
        )
        midnight = datetime.combine(day, time(0, 0), tzinfo=now.tzinfo)
        seconds = (now - midnight).total_seconds() % DAY

        if len(stops) == 1:
            point = stops[0][1]
            return point.kelvin, clamp(point.factor)

        # Umschließendes Paar finden — die Kurve läuft zyklisch über Mitternacht.
        before = stops[-1]
        after = stops[0]
        for index, (stop_seconds, point) in enumerate(stops):
            if stop_seconds > seconds:
                after = (stop_seconds, point)
                before = stops[index - 1] if index else stops[-1]
                break
        else:
            before = stops[-1]
            after = stops[0]

        start_seconds, start = before
        end_seconds, end = after
        span = (end_seconds - start_seconds) % DAY
        if span <= 0:
            span = DAY
        elapsed = (seconds - start_seconds) % DAY
        progress = clamp(elapsed / span)

        kelvin = blend_kelvin(start.kelvin, end.kelvin, progress)
        factor = start.factor + (end.factor - start.factor) * progress
        return int(round(kelvin)), round(clamp(factor), 3)

    # -- Darstellung für die Oberfläche -------------------------------------

    def sample(
        self, day: date, sunrise: datetime, sunset: datetime, steps: int = 96
    ) -> list[dict[str, Any]]:
        """Punkte für den Kurveneditor, alle 15 Minuten."""
        midnight = datetime.combine(day, time(0, 0), tzinfo=sunrise.tzinfo)
        out = []
        for index in range(steps + 1):
            moment = midnight + timedelta(seconds=index * DAY / steps)
            kelvin, factor = self.at_time(moment, sunrise, sunset)
            out.append(
                {
                    "minute": int(index * 1440 / steps),
                    "kelvin": kelvin,
                    "factor": factor,
                }
            )
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "points": [p.to_dict() for p in self.points],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DaylightCurve:
        return cls(
            key=data.get("key", "wohnen"),
            name=data.get("name", "Wohnen"),
            points=[Point.from_dict(p) for p in data.get("points", [])],
        )


# --------------------------------------------------------------------------
# Voreinstellungen je Nutzungsart
# --------------------------------------------------------------------------

DEFAULT_CURVES: dict[str, DaylightCurve] = {
    "wohnen": DaylightCurve(
        "wohnen",
        "Wohnen",
        [
            Point(Anchor.CLOCK, 2200, 0.15, at="00:00"),
            Point(Anchor.SUNRISE, 2700, 0.50),
            Point(Anchor.SUNRISE, 4500, 0.90, offset=90),
            Point(Anchor.NOON, 5500, 1.00),
            Point(Anchor.SUNSET, 4000, 0.90, offset=-120),
            Point(Anchor.SUNSET, 3000, 0.70),
            Point(Anchor.SUNSET, 2400, 0.45, offset=90),
            Point(Anchor.CLOCK, 2200, 0.25, at="23:00"),
        ],
    ),
    "arbeiten": DaylightCurve(
        "arbeiten",
        "Arbeiten",
        [
            Point(Anchor.CLOCK, 2700, 0.40, at="00:00"),
            Point(Anchor.SUNRISE, 4000, 0.80),
            Point(Anchor.SUNRISE, 5500, 1.00, offset=60),
            Point(Anchor.NOON, 6000, 1.00),
            Point(Anchor.SUNSET, 5000, 1.00, offset=-180),
            Point(Anchor.SUNSET, 4000, 0.90),
            Point(Anchor.CLOCK, 3000, 0.60, at="22:00"),
        ],
    ),
    "nassbereich": DaylightCurve(
        "nassbereich",
        "Nassbereich",
        [
            Point(Anchor.CLOCK, 2200, 0.10, at="00:00"),
            Point(Anchor.SUNRISE, 3000, 0.70),
            Point(Anchor.SUNRISE, 4500, 1.00, offset=45),
            Point(Anchor.SUNSET, 4000, 0.90),
            Point(Anchor.SUNSET, 2700, 0.50, offset=60),
            Point(Anchor.CLOCK, 2200, 0.20, at="22:30"),
        ],
    ),
    "verkehrsweg": DaylightCurve(
        "verkehrsweg",
        "Verkehrsweg",
        [
            Point(Anchor.CLOCK, 2200, 0.20, at="00:00"),
            Point(Anchor.SUNRISE, 2700, 0.60),
            Point(Anchor.NOON, 4000, 1.00),
            Point(Anchor.SUNSET, 3000, 0.70),
            Point(Anchor.CLOCK, 2200, 0.30, at="23:00"),
        ],
    ),
}

# Welche Kurve ein Raumtyp voreingestellt bekommt.
KIND_TO_CURVE: dict[str, str] = {
    "wohnraum": "wohnen",
    "essraum": "wohnen",
    "schlafraum": "wohnen",
    "arbeitsraum": "arbeiten",
    "kueche": "arbeiten",
    "nassbereich": "nassbereich",
    "verkehrsweg": "verkehrsweg",
    "nebenraum": "verkehrsweg",
    "aussen": "verkehrsweg",
}
