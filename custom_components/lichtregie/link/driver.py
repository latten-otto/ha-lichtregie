"""Der einzige Ausgang zu den Leuchten.

Sämtliche Stellbefehle laufen hier durch. Das ist keine Formsache, sondern
die Stelle, an der fünf Anforderungen zusammenkommen:

1. Zusammenfassen — Leuchten mit gleichem Zielwert gehen als ein Aufruf
   hinaus, sonst springen Funkleuchten sichtbar nacheinander an.
2. Begrenzen — Aufrufe pro Sekunde gedeckelt, damit das Zigbee- oder
   WLAN-Netz beim Szenenwechsel nicht überläuft.
3. Verifizieren — nach dem Befehl wird die Rückmeldung erwartet; bleibt sie
   aus, wird einmal wiederholt und danach die Leuchte als gestört markiert.
4. Trennen — eigene Befehle werden vermerkt, damit eine Zustandsänderung
   als Fremdeingriff erkannt wird und nicht als eigenes Echo.
5. Überspringen — ein Befehl, der nichts ändert, wird nicht gesendet.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from ..core.scenes import Command

_LOGGER = logging.getLogger(__name__)

# Wie lange ein eigener Befehl als Ursache einer Zustandsänderung gilt.
ECHO_WINDOW = 3.0
# Wie viele Dienstaufrufe pro Sekunde hinausgehen dürfen.
MAX_CALLS_PER_SECOND = 12.0
# Toleranz beim Vergleich von Soll und Ist.
BRIGHTNESS_TOLERANCE = 3


@dataclass
class Expectation:
    """Was nach einem Stellbefehl erwartet wird."""

    entity_id: str
    on: bool
    brightness: int
    kelvin: int | None
    sent_at: float
    retries: int = 0


@dataclass
class DriverStats:
    calls: int = 0
    skipped: int = 0
    grouped: int = 0
    retries: int = 0
    faults: set[str] = field(default_factory=set)


class Driver:
    """Sendet Stellbefehle und überwacht ihre Wirkung."""

    def __init__(self, hass: HomeAssistant, journal) -> None:
        self.hass = hass
        self.journal = journal
        self.stats = DriverStats()
        self._expect: dict[str, Expectation] = {}
        self._budget = MAX_CALLS_PER_SECOND
        self._budget_at = time.monotonic()
        self._lock = asyncio.Lock()

    # -- Senden -------------------------------------------------------------

    async def apply(self, commands: list[Command], zone_id: str = "") -> int:
        """Führt eine Liste von Stellbefehlen aus.

        Rückgabe ist die Zahl der tatsächlich gesendeten Dienstaufrufe.
        """
        pending = [c for c in commands if self._is_change(c)]
        self.stats.skipped += len(commands) - len(pending)
        if not pending:
            return 0

        groups: dict[tuple, list[Command]] = defaultdict(list)
        for command in pending:
            groups[command.key()].append(command)

        sent = 0
        async with self._lock:
            for key, group in groups.items():
                await self._throttle()
                await self._send(group, zone_id)
                sent += 1
                if len(group) > 1:
                    self.stats.grouped += 1
        return sent

    async def _send(self, group: list[Command], zone_id: str) -> None:
        first = group[0]
        entity_ids = [c.entity_id for c in group]
        now = time.monotonic()

        if first.on:
            data: dict = {ATTR_ENTITY_ID: entity_ids}
            if first.brightness:
                data["brightness"] = first.brightness
            if first.kelvin:
                data["color_temp_kelvin"] = first.kelvin
            if first.fade:
                data["transition"] = round(first.fade, 2)
            service = "turn_on"
        else:
            data = {ATTR_ENTITY_ID: entity_ids}
            if first.fade:
                data["transition"] = round(first.fade, 2)
            service = "turn_off"

        for entity_id in entity_ids:
            self._expect[entity_id] = Expectation(
                entity_id=entity_id,
                on=first.on,
                brightness=first.brightness,
                kelvin=first.kelvin,
                sent_at=now,
            )

        self.stats.calls += 1
        try:
            await self.hass.services.async_call(
                "light", service, data, blocking=False
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Stellbefehl fehlgeschlagen: %s", err)
            self.journal.log(
                zone_id,
                "fehler",
                "Stellbefehl fehlgeschlagen",
                str(err),
                entities=entity_ids,
            )
            return

        self.journal.log(
            zone_id,
            "stellbefehl",
            f"{len(entity_ids)} Leuchte(n) {'an' if first.on else 'aus'}",
            (
                f"brightness {first.brightness}"
                + (f" · {first.kelvin} K" if first.kelvin else "")
                + f" · Fade {first.fade:g} s"
                if first.on
                else f"Fade {first.fade:g} s"
            ),
            entities=entity_ids,
            reason=first.reason,
        )

    async def _throttle(self) -> None:
        """Einfaches Token-Bucket gegen Funküberlastung."""
        now = time.monotonic()
        self._budget = min(
            MAX_CALLS_PER_SECOND,
            self._budget + (now - self._budget_at) * MAX_CALLS_PER_SECOND,
        )
        self._budget_at = now
        if self._budget < 1.0:
            await asyncio.sleep((1.0 - self._budget) / MAX_CALLS_PER_SECOND)
            self._budget = 0.0
        else:
            self._budget -= 1.0

    # -- Vergleich mit dem Ist-Zustand -------------------------------------

    def _is_change(self, command: Command) -> bool:
        """Wahr, wenn der Befehl den Zustand tatsächlich ändert."""
        state = self.hass.states.get(command.entity_id)
        if state is None:
            return True
        is_on = state.state == "on"
        if not command.on:
            return is_on
        if not is_on:
            return True
        current = state.attributes.get("brightness")
        if current is None:
            return True
        if abs(int(current) - command.brightness) > BRIGHTNESS_TOLERANCE:
            return True
        if command.kelvin:
            current_kelvin = state.attributes.get("color_temp_kelvin")
            if current_kelvin is None or abs(int(current_kelvin) - command.kelvin) > 60:
                return True
        return False

    # -- Fremdeingriffe -----------------------------------------------------

    def was_ours(self, entity_id: str, now: float | None = None) -> bool:
        """Wahr, wenn diese Änderung auf einen eigenen Befehl zurückgeht."""
        expectation = self._expect.get(entity_id)
        if expectation is None:
            return False
        now = now if now is not None else time.monotonic()
        return now - expectation.sent_at <= ECHO_WINDOW

    def forget(self, entity_id: str) -> None:
        self._expect.pop(entity_id, None)

    # -- Verifikation -------------------------------------------------------

    async def verify(self) -> list[str]:
        """Prüft offene Erwartungen und wiederholt einmal.

        Wird vom Taktgeber aufgerufen. Rückgabe sind die Entitäten, die
        endgültig als gestört gelten.
        """
        now = time.monotonic()
        faults: list[str] = []

        for entity_id, expectation in list(self._expect.items()):
            age = now - expectation.sent_at
            if age < 1.5:
                continue

            state = self.hass.states.get(entity_id)
            ok = state is not None and (
                (state.state == "on") == expectation.on
                and (
                    not expectation.on
                    or state.attributes.get("brightness") is None
                    or abs(
                        int(state.attributes.get("brightness") or 0)
                        - expectation.brightness
                    )
                    <= BRIGHTNESS_TOLERANCE * 3
                )
            )

            if ok:
                self._expect.pop(entity_id, None)
                self.stats.faults.discard(entity_id)
                continue

            if age > 6.0:
                self._expect.pop(entity_id, None)
                self.stats.faults.add(entity_id)
                faults.append(entity_id)
                self.journal.log(
                    "",
                    "stoerung",
                    "Leuchte antwortet nicht",
                    f"{entity_id} meldet den erwarteten Zustand nicht",
                    entity_id=entity_id,
                )
            elif expectation.retries == 0:
                expectation.retries = 1
                expectation.sent_at = now
                self.stats.retries += 1
                data: dict = {ATTR_ENTITY_ID: entity_id}
                if expectation.on:
                    if expectation.brightness:
                        data["brightness"] = expectation.brightness
                    if expectation.kelvin:
                        data["color_temp_kelvin"] = expectation.kelvin
                await self.hass.services.async_call(
                    "light",
                    "turn_on" if expectation.on else "turn_off",
                    data,
                    blocking=False,
                )

        return faults
