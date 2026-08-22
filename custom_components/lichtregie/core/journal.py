"""Entscheidungsprotokoll.

Jede Entscheidung wird mit ihrer Begründung festgehalten: was ausgelöst hat,
welche Messwerte vorlagen, welche Ebene gewonnen hat, was gesendet wurde und
was das Gerät gemeldet hat. Das ist der Unterschied zwischen „das Licht ging
komisch an" und einer Diagnose in zwei Minuten.

Gehalten wird ein Ringpuffer im Arbeitsspeicher; die Oberfläche liest ihn
über die Schnittstelle und kann ihn als CSV ausgeben.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

__all__ = ["Entry", "Journal"]

MAX_ENTRIES = 2000


@dataclass
class Entry:
    """Ein Protokolleintrag."""

    at: float
    zone_id: str
    kind: str  # einschalten · stellbefehl · abweichung · ablauf · fehler …
    headline: str
    detail: str = ""
    layer: int | None = None
    scene_id: str | None = None
    lux: float | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Journal:
    """Ringpuffer der Entscheidungen."""

    def __init__(self, maxlen: int = MAX_ENTRIES) -> None:
        self._entries: deque[Entry] = deque(maxlen=maxlen)
        self._listeners: list[Any] = []

    def log(
        self,
        zone_id: str,
        kind: str,
        headline: str,
        detail: str = "",
        *,
        layer: int | None = None,
        scene_id: str | None = None,
        lux: float | None = None,
        at: float | None = None,
        **data: Any,
    ) -> Entry:
        entry = Entry(
            at=at if at is not None else time.time(),
            zone_id=zone_id,
            kind=kind,
            headline=headline,
            detail=detail,
            layer=layer,
            scene_id=scene_id,
            lux=lux,
            data=data,
        )
        self._entries.append(entry)
        for callback in list(self._listeners):
            try:
                callback(entry)
            except Exception:  # noqa: BLE001 - ein Zuhörer darf nichts kaputt machen
                self._listeners.remove(callback)
        return entry

    def subscribe(self, callback: Any) -> Any:
        """Meldet einen Zuhörer an und gibt die Abmeldefunktion zurück."""
        self._listeners.append(callback)

        def unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return unsubscribe

    def recent(
        self,
        zone_id: str | None = None,
        limit: int = 200,
        since: float | None = None,
    ) -> list[dict[str, Any]]:
        out: Iterable[Entry] = reversed(self._entries)
        rows = []
        for entry in out:
            if zone_id and entry.zone_id != zone_id:
                continue
            if since is not None and entry.at < since:
                break
            rows.append(entry.to_dict())
            if len(rows) >= limit:
                break
        return rows

    def as_csv(self, zone_id: str | None = None) -> str:
        head = "zeit;zone;art;ereignis;detail;ebene;szene;lux\n"
        lines = [head]
        for row in reversed(self.recent(zone_id, limit=len(self._entries))):
            lines.append(
                ";".join(
                    str(x if x is not None else "")
                    for x in (
                        time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row["at"])),
                        row["zone_id"],
                        row["kind"],
                        row["headline"].replace(";", ","),
                        row["detail"].replace(";", ","),
                        row["layer"],
                        row["scene_id"],
                        row["lux"],
                    )
                )
                + "\n"
            )
        return "".join(lines)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
