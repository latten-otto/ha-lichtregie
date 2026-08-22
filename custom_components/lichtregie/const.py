"""Konstanten der Lichtregie."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "lichtregie"
PANEL_URL: Final = "/lichtregie-panel"
PANEL_TITLE: Final = "Lichtregie"
PANEL_ICON: Final = "mdi:lightbulb-group-outline"
STORAGE_KEY: Final = "lichtregie.config"
STORAGE_VERSION: Final = 1

# --- Lichtrollen -----------------------------------------------------------
ROLE_GENERAL: Final = "general"  # Grundlicht
ROLE_TASK: Final = "task"  # Arbeitslicht
ROLE_AMBIENT: Final = "ambient"  # Stimmungslicht
ROLE_ACCENT: Final = "accent"  # Akzentlicht
ROLE_NIGHT: Final = "night"  # Orientierungslicht
ROLE_EFFECT: Final = "effect"  # Effekt / Farbe

ROLES: Final = (
    ROLE_GENERAL,
    ROLE_TASK,
    ROLE_AMBIENT,
    ROLE_ACCENT,
    ROLE_NIGHT,
    ROLE_EFFECT,
)

ROLE_LABELS: Final = {
    ROLE_GENERAL: "Grundlicht",
    ROLE_TASK: "Arbeitslicht",
    ROLE_AMBIENT: "Stimmungslicht",
    ROLE_ACCENT: "Akzentlicht",
    ROLE_NIGHT: "Orientierung",
    ROLE_EFFECT: "Effekt",
}

# --- Ebenen des Prioritätsstapels -----------------------------------------
LAYER_SAFETY: Final = 99
LAYER_BLOCK: Final = 80
LAYER_MANUAL: Final = 60
LAYER_SCENE: Final = 50
LAYER_PRESENCE: Final = 40
LAYER_SCHEDULE: Final = 30
LAYER_DAYLIGHT: Final = 20
LAYER_BASE: Final = 10

LAYER_LABELS: Final = {
    LAYER_SAFETY: "Störung & Sicherheit",
    LAYER_BLOCK: "Sperre",
    LAYER_MANUAL: "Manueller Eingriff",
    LAYER_SCENE: "Szenenaufruf",
    LAYER_PRESENCE: "Anwesenheitsregel",
    LAYER_SCHEDULE: "Zeitplan",
    LAYER_DAYLIGHT: "Tagesverlauf",
    LAYER_BASE: "Grundzustand",
}

# --- Zustände einer Zone ---------------------------------------------------
STATE_EMPTY: Final = "leer"
STATE_ARRIVAL: Final = "ankunft"
STATE_OCCUPIED: Final = "belegt"
STATE_EXTENDED: Final = "vertieft"
STATE_FADING: Final = "auslauf"
STATE_NIGHT: Final = "nachtfenster"
STATE_LOCKED: Final = "gesperrt"

# --- Haltemodelle einer Bindung -------------------------------------------
HOLD_WHILE_OCCUPIED: Final = "solange_belegt"
HOLD_FIXED: Final = "feste_dauer"
HOLD_UNTIL_EMPTY: Final = "bis_leer"
HOLD_UNTIL_PRESS: Final = "bis_gegendruck"
HOLD_UNTIL_TIME: Final = "bis_zeitpunkt"
HOLD_UNTIL_SCENE: Final = "bis_andere_szene"
HOLD_FOREVER: Final = "unbegrenzt"

HOLD_MODES: Final = (
    HOLD_WHILE_OCCUPIED,
    HOLD_FIXED,
    HOLD_UNTIL_EMPTY,
    HOLD_UNTIL_PRESS,
    HOLD_UNTIL_TIME,
    HOLD_UNTIL_SCENE,
    HOLD_FOREVER,
)

# --- Normalisierte Gesten --------------------------------------------------
GESTURE_TAP: Final = "tippen"
GESTURE_DOUBLE: Final = "doppelt"
GESTURE_TRIPLE: Final = "dreifach"
GESTURE_HOLD: Final = "halten"
GESTURE_RELEASE: Final = "loslassen"
GESTURE_LONG: Final = "lang"

GESTURES: Final = (
    GESTURE_TAP,
    GESTURE_DOUBLE,
    GESTURE_TRIPLE,
    GESTURE_HOLD,
    GESTURE_RELEASE,
    GESTURE_LONG,
)

# Fenster, in dem aufeinanderfolgende Tipper zu Doppel/Dreifach werden.
MULTI_TAP_WINDOW: Final = 0.4
# Ab dieser Druckdauer gilt ein Binäreingang als "lang".
LONG_PRESS_AFTER: Final = 0.6

# --- Takte -----------------------------------------------------------------
TICK_FAST: Final = 0.25  # Reaktionen, Timer
TICK_CONTROL: Final = 10.0  # Konstantlichtregelung

# --- Dimmkurven ------------------------------------------------------------
CURVE_LINEAR: Final = "linear"
CURVE_GAMMA: Final = "gamma"
CURVE_LOG: Final = "log"
CURVE_DALI: Final = "dali"
CURVES: Final = (CURVE_LOG, CURVE_GAMMA, CURVE_LINEAR, CURVE_DALI)

CURVE_LABELS: Final = {
    CURVE_LOG: "Logarithmisch über den Regelbereich",
    CURVE_GAMMA: "Wahrnehmung (Gamma 2,2)",
    CURVE_LINEAR: "Linear zum Lichtstrom",
    CURVE_DALI: "DALI nach IEC 62386-102",
}

DEFAULT_CURVE: Final = CURVE_LOG
DEFAULT_GAMMA: Final = 2.2

# Kleinster Lichtstrom, mit dem die logarithmische Kurve rechnet, wenn fuer
# eine Leuchte kein Minimalwert gemessen wurde. 1/255 sind 0,39 % — darunter
# kann der 8-Bit-Stellwert nichts mehr unterscheiden.
FLOOR_FLUX: Final = 1.0 / 255.0

# --- Fade-Zeiten in Sekunden ----------------------------------------------
FADE_MOTION: Final = 0.3
FADE_SCENE: Final = 1.5
FADE_OFF: Final = 2.0
FADE_TRACKING: Final = 30.0

# Maximale Änderung pro Sekunde bei automatischer Nachführung (unsichtbar).
MAX_TRACKING_RATE: Final = 0.01
