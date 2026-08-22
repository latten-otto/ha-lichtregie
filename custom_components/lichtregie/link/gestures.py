"""Normalisierung der Bedienereignisse.

In einer gewachsenen Anlage meldet sich jedes Fabrikat anders:

* Busch-Jaeger RB01/RM01 über deCONZ liefern nur ``short_release``,
  ``long_press`` und ``long_release`` — keinen kurzen Druck, keinen
  Doppelklick.
* Philips Hue RWL022 liefert zusätzlich ``short_press``.
* Shelly-Eingänge liefern als Ereignis-Entität ``single_push``,
  ``double_push``, ``triple_push``, ``long_push``, ``btn_down``, ``btn_up``.
* Der Shelly i4 meldet über binäre Sensoren gar keine Geste, sondern nur
  „Eingang zu“ und „Eingang offen“.
* IKEA Trådfri meldet nur ``initial_press``.

Diese Klasse bildet alles auf ein gemeinsames Vokabular ab und ergänzt
fehlende Gesten selbst: Mehrfachtippen aus aufeinanderfolgenden Einzel-
ereignissen, Halten aus dem Paar aus langem Druck und Loslassen, und beim
reinen Kontakt aus der Länge der Flanke.

Die Klasse kennt keine Zeitgeber — die Zeit wird übergeben, verzögerte
Auswertungen meldet sie über :meth:`due`. Dadurch ist sie eigenständig
testbar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..const import (
    GESTURE_DOUBLE,
    GESTURE_HOLD,
    GESTURE_LONG,
    GESTURE_RELEASE,
    GESTURE_TAP,
    GESTURE_TRIPLE,
    LONG_PRESS_AFTER,
    MULTI_TAP_WINDOW,
)

__all__ = ["ButtonEvent", "GestureRecognizer"]


@dataclass(frozen=True)
class ButtonEvent:
    """Eine erkannte Geste."""

    control_id: str
    button: str
    gesture: str
    at: float
    raw: str = ""

    @property
    def key(self) -> str:
        return f"{self.button}:{self.gesture}"


# Rohereignisse, die unmittelbar eine Geste ergeben.
_DIRECT = {
    "double_push": GESTURE_DOUBLE,
    "double_press": GESTURE_DOUBLE,
    "triple_push": GESTURE_TRIPLE,
    "triple_press": GESTURE_TRIPLE,
    "long_push": GESTURE_LONG,
    "hold_press": GESTURE_HOLD,
}

# Rohereignisse, die einen einzelnen Tipper bedeuten und deshalb erst nach
# dem Mehrfach-Fenster ausgewertet werden.
_TAPS = {
    "short_release",
    "remote_button_short_release",
    "single_push",
    "press",
    "initial_press",
    "short_press",
}

_HOLD_START = {
    "long_press",
    "remote_button_long_press",
    "brightness_step_up",
    "brightness_step_down",
}

_HOLD_END = {
    "long_release",
    "remote_button_long_release",
    "brightness_stop",
}


class GestureRecognizer:
    """Erkennt Gesten aus den Rohereignissen eines Bedienelements."""

    def __init__(
        self,
        multi_tap_window: float = MULTI_TAP_WINDOW,
        long_press_after: float = LONG_PRESS_AFTER,
    ) -> None:
        self.window = multi_tap_window
        self.long_after = long_press_after
        # button -> (Anzahl Tipper, Zeit des ersten, Rohname)
        self._pending: dict[str, tuple[int, float, str]] = {}
        # button -> Zeitpunkt der schließenden Flanke
        self._down_since: dict[str, float] = {}
        self._holding: set[str] = set()

    # -- Eingang ------------------------------------------------------------

    def feed(
        self, control_id: str, button: str, raw: str, now: float
    ) -> list[ButtonEvent]:
        """Nimmt ein Rohereignis entgegen und liefert fertige Gesten.

        Ein Tipper wird nicht sofort gemeldet, weil daraus noch ein
        Doppel- oder Dreifachtippen werden kann. Der Aufrufer muss deshalb
        :meth:`due` regelmäßig aufrufen.
        """
        raw = (raw or "").lower()
        out: list[ButtonEvent] = []

        if raw in _DIRECT:
            out.append(
                ButtonEvent(control_id, button, _DIRECT[raw], now, raw)
            )
            self._pending.pop(button, None)
            return out

        if raw in _HOLD_START:
            self._pending.pop(button, None)
            self._holding.add(button)
            out.append(ButtonEvent(control_id, button, GESTURE_HOLD, now, raw))
            return out

        if raw in _HOLD_END:
            if button in self._holding:
                self._holding.discard(button)
                out.append(
                    ButtonEvent(control_id, button, GESTURE_RELEASE, now, raw)
                )
            return out

        if raw in _TAPS:
            count, first, _ = self._pending.get(button, (0, now, raw))
            self._pending[button] = (min(3, count + 1), first, raw)
            return out

        # Unbekanntes Rohereignis wie einen Tipper behandeln, damit auch
        # exotische Fabrikate bedienbar bleiben.
        count, first, _ = self._pending.get(button, (0, now, raw))
        self._pending[button] = (min(3, count + 1), first, raw)
        return out

    def feed_binary(
        self, control_id: str, button: str, closed: bool, now: float
    ) -> list[ButtonEvent]:
        """Für Eingänge, die nur „zu“ und „offen“ melden.

        Aus der Länge der Flanke entsteht Tippen oder langer Druck; ein
        gehaltener Kontakt löst nach der Schwelle sofort Halten aus, damit
        Dimmen funktioniert.
        """
        out: list[ButtonEvent] = []
        if closed:
            self._down_since[button] = now
            return out

        started = self._down_since.pop(button, None)
        if started is None:
            return out

        if button in self._holding:
            self._holding.discard(button)
            return [ButtonEvent(control_id, button, GESTURE_RELEASE, now, "edge")]

        if now - started >= self.long_after:
            out.append(ButtonEvent(control_id, button, GESTURE_LONG, now, "edge"))
        else:
            count, first, _ = self._pending.get(button, (0, now, "edge"))
            self._pending[button] = (min(3, count + 1), first, "edge")
        return out

    # -- Verzögerte Auswertung ---------------------------------------------

    def due(self, control_id: str, now: float) -> list[ButtonEvent]:
        """Liefert Gesten, deren Wartefenster abgelaufen ist."""
        out: list[ButtonEvent] = []

        for button, (count, first, raw) in list(self._pending.items()):
            if now - first < self.window:
                continue
            self._pending.pop(button, None)
            gesture = {1: GESTURE_TAP, 2: GESTURE_DOUBLE, 3: GESTURE_TRIPLE}[count]
            out.append(ButtonEvent(control_id, button, gesture, now, raw))

        for button, started in list(self._down_since.items()):
            if button in self._holding:
                continue
            if now - started >= self.long_after:
                self._holding.add(button)
                out.append(ButtonEvent(control_id, button, GESTURE_HOLD, now, "edge"))

        return out

    @property
    def waiting(self) -> bool:
        """Wahr, solange eine Auswertung aussteht."""
        return bool(self._pending or self._down_since)

    def reset(self) -> None:
        self._pending.clear()
        self._down_since.clear()
        self._holding.clear()


def describe_source(payload: dict[str, Any]) -> tuple[str, str]:
    """Zerlegt ein Rohereignis in Taste und Aktion.

    Deckt die Formate ab, die in dieser Anlage vorkommen. Unbekanntes wird
    nicht verworfen, sondern als Taste ``1`` mit dem Rohnamen gemeldet —
    im Lernmodus sieht der Bediener dann, was ankam.
    """
    # deCONZ-Geräteauslöser: {"type": "remote_button_short_release",
    #                         "subtype": "button_3"}
    if "subtype" in payload and "type" in payload:
        return str(payload["subtype"]), str(payload["type"])

    # deCONZ-Rohereignis mit Zahlencode: 1002 = Taste 1, kurz losgelassen
    if "event" in payload:
        code = int(payload["event"])
        button = str(code // 1000)
        action = {
            0: "initial_press",
            1: "long_press",
            2: "short_release",
            3: "long_release",
            4: "double_press",
        }.get(code % 1000, str(code % 1000))
        return button, action

    # Ereignis-Entität: {"event_type": "double_push"}
    if "event_type" in payload:
        return str(payload.get("button", "1")), str(payload["event_type"])

    return "1", str(payload)


def normalize_source_events(
    recognizer: GestureRecognizer,
    control_id: str,
    payload: dict[str, Any],
    now: float,
    emit: Callable[[ButtonEvent], None],
) -> None:
    """Bequemer Weg vom Rohereignis zur gemeldeten Geste."""
    button, action = describe_source(payload)
    for event in recognizer.feed(control_id, button, action, now):
        emit(event)
