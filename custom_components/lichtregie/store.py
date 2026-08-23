"""Persistenz mit Versionierung.

Die Konfiguration liegt als JSON im Speicherverzeichnis von Home Assistant.
Jede Änderung erzeugt eine neue Fassung; die letzten Fassungen bleiben
erhalten, damit sich ein Stand zurückholen lässt.
"""

from __future__ import annotations

import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

import logging

from .const import STORAGE_KEY, STORAGE_VERSION
from .core.migrate import migrate_installation
from .core.model import Installation

_LOGGER = logging.getLogger(__name__)

KEEP_REVISIONS = 20
RUNTIME_KEY = "lichtregie.runtime"


class ConfigStore:
    """Lädt und speichert die Anlage."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._revisions: list[dict[str, Any]] = []
        self.installation = Installation()

    async def load(self) -> Installation:
        data = await self._store.async_load()
        if data:
            roh = data.get("installation", {})
            roh, umgerechnet = migrate_installation(roh)
            self.installation = Installation.from_dict(roh)
            self._revisions = data.get("revisions", [])
            if umgerechnet:
                _LOGGER.info(
                    "%s Szene(n) auf Rollenwerte umgerechnet", umgerechnet
                )
                await self.save(label="Szenen auf Rollenwerte umgestellt")
        return self.installation

    async def save(self, label: str = "", author: str = "") -> None:
        payload = self.installation.to_dict()
        self._revisions.append(
            {
                "at": time.time(),
                "label": label,
                "author": author,
                "version": self.installation.version,
                "installation": payload,
            }
        )
        self._revisions = self._revisions[-KEEP_REVISIONS:]
        self.installation.version += 1
        await self._store.async_save(
            {
                "installation": self.installation.to_dict(),
                "revisions": self._revisions,
            }
        )

    def revisions(self) -> list[dict[str, Any]]:
        return [
            {
                "at": r["at"],
                "label": r.get("label", ""),
                "author": r.get("author", ""),
                "version": r.get("version"),
            }
            for r in reversed(self._revisions)
        ]

    async def rollback(self, version: int) -> bool:
        """Holt eine frühere Fassung zurück."""
        for revision in reversed(self._revisions):
            if revision.get("version") == version:
                self.installation = Installation.from_dict(revision["installation"])
                await self.save(label=f"Rückkehr zu Fassung {version}")
                return True
        return False


class RuntimeStore:
    """Sichert den Laufzeitzustand über einen Neustart.

    Ohne das stünde nach jedem Update jeder Raum wieder im Grundzustand —
    mitten in einem Abend, an dem jemand eine Szene aufgerufen hat.
    Gespeichert werden die Anmeldungen des Stapels mit ihrer Restlaufzeit,
    der Zustand der Zone und eine laufende Sperrzeit.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store = Store(hass, 1, RUNTIME_KEY)
        self._data: dict[str, Any] = {}

    async def load(self) -> dict[str, Any]:
        self._data = await self._store.async_load() or {}
        return self._data

    async def save(self, zones: dict[str, Any]) -> None:
        self._data = {"at": time.time(), "zones": zones}
        await self._store.async_save(self._data)

    def zones(self) -> dict[str, Any]:
        return self._data.get("zones", {})

    def age(self) -> float:
        """Wie alt der gesicherte Zustand ist, in Sekunden."""
        saved = self._data.get("at")
        return time.time() - saved if saved else 1e9
