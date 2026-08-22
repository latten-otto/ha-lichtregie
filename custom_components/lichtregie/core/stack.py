"""Der Prioritätsstapel einer Zone.

Jede Ebene kann einen Sollwert anmelden. Ausgegeben wird immer die aktive
Ebene mit der höchsten Priorität. Jede Anmeldung trägt eine Laufzeit; läuft
sie ab, fällt die Ausgabe automatisch auf die nächste Ebene darunter.

Der Stapel kennt keine Lampen und keine Zeitgeber — er bekommt die aktuelle
Zeit übergeben. Dadurch ist er vollständig ohne Home Assistant testbar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..const import LAYER_BASE, LAYER_LABELS

__all__ = ["Claim", "PriorityStack"]


@dataclass
class Claim:
    """Die Anmeldung einer Ebene."""

    layer: int
    scene_id: str | None = None
    levels: dict[str, float] = field(default_factory=dict)
    kelvin: dict[str, int] = field(default_factory=dict)
    fade: float = 1.5
    source: str = ""  # was ausgelöst hat, für das Protokoll
    expires_at: float | None = None  # None heißt: läuft nicht ab
    hold: str = ""  # Haltemodell, für die Anzeige
    then: str = "automatik"
    started_at: float = 0.0

    def remaining(self, now: float) -> float | None:
        if self.expires_at is None:
            return None
        return max(0.0, self.expires_at - now)

    def store(self, now: float) -> dict[str, Any]:
        """Fassung zum Sichern über einen Neustart.

        Die Ablaufzeit wird als Restlaufzeit gespeichert: ``expires_at``
        beruht auf der monotonen Uhr des Prozesses und ist nach einem
        Neustart wertlos.
        """
        return {
            "layer": self.layer,
            "scene_id": self.scene_id,
            "levels": dict(self.levels),
            "kelvin": dict(self.kelvin),
            "fade": self.fade,
            "source": self.source,
            "hold": self.hold,
            "then": self.then,
            "remaining": self.remaining(now),
        }

    @classmethod
    def restore(cls, data: dict[str, Any], now: float) -> Claim:
        """Gegenstück zu :meth:`store`."""
        remaining = data.get("remaining")
        return cls(
            layer=int(data["layer"]),
            scene_id=data.get("scene_id"),
            levels={k: float(v) for k, v in (data.get("levels") or {}).items()},
            kelvin={k: int(v) for k, v in (data.get("kelvin") or {}).items()},
            fade=float(data.get("fade", 1.5)),
            source=data.get("source", ""),
            hold=data.get("hold", ""),
            then=data.get("then", "automatik"),
            expires_at=(now + float(remaining)) if remaining is not None else None,
            started_at=now,
        )

    def to_dict(self, now: float) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "label": LAYER_LABELS.get(self.layer, str(self.layer)),
            "scene_id": self.scene_id,
            "source": self.source,
            "hold": self.hold,
            "fade": self.fade,
            "remaining": self.remaining(now),
            "levels": dict(self.levels),
        }


class PriorityStack:
    """Hält die Anmeldungen einer Zone."""

    def __init__(self) -> None:
        self._claims: dict[int, Claim] = {}

    # -- Anmelden und Freigeben --------------------------------------------

    def push(self, claim: Claim, now: float = 0.0) -> None:
        """Meldet eine Ebene an und ersetzt eine vorhandene Anmeldung."""
        claim.started_at = now
        self._claims[claim.layer] = claim

    def release(self, layer: int) -> Claim | None:
        """Gibt eine Ebene frei."""
        return self._claims.pop(layer, None)

    def release_above(self, layer: int) -> list[Claim]:
        """Gibt alle Ebenen oberhalb einer Grenze frei — für „alles aus“."""
        gone = [c for lv, c in self._claims.items() if lv > layer]
        for claim in gone:
            self._claims.pop(claim.layer, None)
        return gone

    def clear(self) -> None:
        self._claims.clear()

    # -- Ablauf -------------------------------------------------------------

    def expire(self, now: float) -> list[Claim]:
        """Entfernt abgelaufene Anmeldungen und gibt sie zurück."""
        gone = [
            claim
            for claim in self._claims.values()
            if claim.expires_at is not None and claim.expires_at <= now
        ]
        for claim in gone:
            self._claims.pop(claim.layer, None)
        return gone

    def extend(self, layer: int, seconds: float, now: float) -> bool:
        """Verlängert eine laufende Anmeldung — etwa bei erneuter Bewegung."""
        claim = self._claims.get(layer)
        if claim is None:
            return False
        claim.expires_at = now + seconds
        return True

    # -- Abfragen -----------------------------------------------------------

    def get(self, layer: int) -> Claim | None:
        return self._claims.get(layer)

    def has(self, layer: int) -> bool:
        return layer in self._claims

    @property
    def active(self) -> Claim | None:
        """Die Anmeldung, die gerade die Ausgabe bestimmt."""
        if not self._claims:
            return None
        return self._claims[max(self._claims)]

    @property
    def layers(self) -> list[int]:
        return sorted(self._claims, reverse=True)

    def covers(self, circuit_id: str) -> int | None:
        """Welche Ebene diesen Kreis gerade bestimmt.

        Nicht jede Anmeldung nennt jeden Kreis. Eine Szene, die nur das
        Stimmungslicht setzt, überlässt den Rest den Ebenen darunter.
        """
        for layer in sorted(self._claims, reverse=True):
            if circuit_id in self._claims[layer].levels:
                return layer
        return None

    def resolve(self) -> tuple[dict[str, float], dict[str, int], float]:
        """Rechnet den Stapel zu einem Sollbild zusammen.

        Von unten nach oben, damit höhere Ebenen die niedrigeren
        überschreiben, ohne deren Kreise zu löschen.
        """
        levels: dict[str, float] = {}
        kelvin: dict[str, int] = {}
        fade = 1.5
        for layer in sorted(self._claims):
            claim = self._claims[layer]
            levels.update(claim.levels)
            kelvin.update(claim.kelvin)
            fade = claim.fade
        return levels, kelvin, fade

    def snapshot(self, now: float) -> list[dict[str, Any]]:
        """Zustand für die Oberfläche."""
        active = self.active
        out = []
        for layer in sorted(LAYER_LABELS, reverse=True):
            claim = self._claims.get(layer)
            out.append(
                {
                    "layer": layer,
                    "label": LAYER_LABELS[layer],
                    "active": claim is not None and claim is active,
                    "claimed": claim is not None,
                    "source": claim.source if claim else "",
                    "scene_id": claim.scene_id if claim else None,
                    "remaining": claim.remaining(now) if claim else None,
                    "hold": claim.hold if claim else "",
                }
            )
        return out

    def store(self, now: float) -> list[dict[str, Any]]:
        """Alle Anmeldungen sichern."""
        return [claim.store(now) for claim in self._claims.values()]

    def restore(self, rows: list[dict[str, Any]], now: float) -> None:
        """Gesicherte Anmeldungen zurückholen."""
        self._claims.clear()
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            try:
                claim = Claim.restore(row, now)
            except (AttributeError, KeyError, TypeError, ValueError):
                continue
            self._claims[claim.layer] = claim

    def base_only(self) -> bool:
        """Wahr, wenn nichts oberhalb des Grundzustands angemeldet ist."""
        return all(layer <= LAYER_BASE for layer in self._claims)
