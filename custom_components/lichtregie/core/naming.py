"""Benennung und Einordnung — reine Logik, ohne Home Assistant.

Aus dem Namen einer Leuchte und ihres Bereichs wird geschlossen, welche
Aufgabe sie hat und welcher Raumtyp vorliegt. Das ist ein Vorschlag, kein
Urteil: die Oberfläche zeigt ihn an, der Bediener bestätigt.

Die Wortlisten sind an einer echten Anlage mit 45 Leuchten geprüft.
"""

from __future__ import annotations

from typing import Any

from ..const import (
    ROLE_ACCENT,
    ROLE_AMBIENT,
    ROLE_GENERAL,
    ROLE_NIGHT,
    ROLE_TASK,
)

__all__ = [
    "guess_role",
    "guess_kind",
    "is_room_lighting",
    "is_group",
    "KIND_DEFAULTS",
]


# --- Rollenerkennung aus dem Namen ----------------------------------------

# Die Reihenfolge entscheidet: der erste Treffer gewinnt. Stimmungslicht
# steht deshalb vor Arbeitslicht — sonst würde „Kochinsel Ambientebeleuchtung"
# über das Wort „insel" zum Arbeitslicht.
_ROLE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        ROLE_AMBIENT,
        (
            "voute",
            "indirekt",
            "ambiente",
            "stimmung",
            "uplight",
            "wandflut",
            "lichtband",
            "strip",
            "streifen",
            "wandlampe",
            "wandleuchte",
            "bett",
        ),
    ),
    (
        ROLE_TASK,
        (
            "unterschrank",
            "arbeits",
            "spiegel",
            "schreibtisch",
            "lese",
            "spuel",
            "spül",
            "kochfeld",
            "kuechenzeile",
            "küchenzeile",
            "werkbank",
            "insel",
            "pendel",
            "esstisch",
        ),
    ),
    (
        ROLE_ACCENT,
        (
            "deko",
            "bild",
            "vitrine",
            "pflanze",
            "regal",
            "schrankbeleuchtung",
            "akzent",
            "kamin",
        ),
    ),
    (
        ROLE_NIGHT,
        ("nacht", "sockel", "stufe", "orientier", "treppenlicht", "unterbett"),
    ),
    (
        ROLE_GENERAL,
        ("spot", "decke", "hauptlicht", "raumlicht", "leuchte", "lampe", "licht"),
    ),
)

# --- Raumtyp aus dem Bereichsnamen ----------------------------------------

_KIND_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("verkehrsweg", ("flur", "diele", "treppe", "gang", "eingang")),
    ("nassbereich", ("bad", "dusche", "wc", "waschraum")),
    ("kueche", ("küche", "kuche", "kueche")),
    ("essraum", ("esszimmer", "essplatz")),
    ("arbeitsraum", ("büro", "buro", "arbeitszimmer", "werkstatt")),
    ("schlafraum", ("schlafzimmer", "kinderzimmer", "gästezimmer", "ankleide")),
    ("nebenraum", ("keller", "abstellkammer", "speisekammer", "garage", "hwr")),
    ("aussen", ("draußen", "draussen", "garten", "terrasse", "carport")),
)

# Vorgaben je Raumtyp: Sollwert, Einschalt- und Freigabeschwelle, Nachlauf.
KIND_DEFAULTS: dict[str, dict[str, float]] = {
    "wohnraum": {"setpoint_lux": 150, "on_below": 300, "off_above": 380, "linger": 1200},
    "verkehrsweg": {"setpoint_lux": 100, "on_below": 200, "off_above": 260, "linger": 180},
    "nassbereich": {"setpoint_lux": 200, "on_below": 180, "off_above": 240, "linger": 480},
    "kueche": {"setpoint_lux": 300, "on_below": 250, "off_above": 320, "linger": 600},
    "essraum": {"setpoint_lux": 200, "on_below": 250, "off_above": 320, "linger": 900},
    "arbeitsraum": {"setpoint_lux": 500, "on_below": 400, "off_above": 500, "linger": 1800},
    "schlafraum": {"setpoint_lux": 100, "on_below": 200, "off_above": 260, "linger": 600},
    "nebenraum": {"setpoint_lux": 150, "on_below": 200, "off_above": 260, "linger": 300},
    "aussen": {"setpoint_lux": 50, "on_below": 40, "off_above": 80, "linger": 300},
}


# Leuchten, die keine Raumbeleuchtung sind. Sie werden eingelesen, aber
# abgeschaltet angelegt, damit keine Szene sie versehentlich mitschaltet.
_NOT_ROOM_LIGHTING: tuple[str, ...] = (
    "flutlicht",
    "kamera",
    "hintergrundbeleuchtung",
    "statuslicht",
    "nachtsicht",
    "infrarot",
    "luftreiniger",
    "bildschirm",
    "display",
)


def is_room_lighting(name: str) -> bool:
    """Falsch für Leuchten, die den Raum nicht beleuchten sollen."""
    lowered = name.lower()
    return not any(word in lowered for word in _NOT_ROOM_LIGHTING)


def guess_role(name: str, capabilities: dict[str, Any]) -> str:
    """Schlägt eine Rolle vor — aus dem Namen, sonst aus den Fähigkeiten."""
    lowered = name.lower()
    for role, words in _ROLE_HINTS:
        if any(word in lowered for word in words):
            return role
    # Ein reiner Schalter ohne Dimmung ist fast immer Grundlicht.
    if not capabilities.get("dimmable"):
        return ROLE_GENERAL
    return ROLE_GENERAL


def is_group(state, device) -> bool:
    """Wahr, wenn diese Leuchte in Wirklichkeit eine Gruppe ist.

    Gruppen dürfen nicht als Lichtkreis auftauchen: sie steuern dieselben
    Leuchten wie die Einzeleinträge, und die Engine würde jede Lampe zweimal
    ansprechen — einmal direkt, einmal über die Gruppe.

    Zwei Bauarten kommen vor: Lichtgruppen von Home Assistant, die ihre
    Mitglieder im Attribut ``entity_id`` führen, und Gruppen der
    Zigbee-Integration, die als eigenes Gerät mit dem Modell „deCONZ group"
    im Register stehen.
    """
    if state is not None and state.attributes.get("entity_id"):
        return True
    if device is not None and "group" in (device.model or "").lower():
        return True
    return False


def guess_kind(area_name: str) -> str:
    lowered = area_name.lower()
    for kind, words in _KIND_HINTS:
        if any(word in lowered for word in words):
            return kind
    return "wohnraum"


# --------------------------------------------------------------------------
# Bedienelemente erkennen
# --------------------------------------------------------------------------

# Auslösertypen, die wirklich von einem Taster kommen. Bewusst als
# Positivliste, nicht als Suchmuster: eine Suche nach „press" trifft auch
# „pressure" (jeder Umweltsensor), und eine Suche nach „button" trifft
# Geräte, deren Knopf nichts mit Beleuchtung zu tun hat.
#
# Nicht enthalten ist der Typ „pressed" allein. Den melden Sonos-Lautsprecher
# und Miele-Hausgeräte für ihre Gerätetaste — technisch ein Taster, als
# Lichtschalter aber unsinnig.
_BUTTON_SUFFIXES: tuple[str, ...] = ("_push", "_click")
_BUTTON_TYPES: frozenset[str] = frozenset(
    {
        "button",
        "single_press",
        "double_press",
        "triple_press",
        "long_press",
        "hold_press",
        "short_press",
        "click",
    }
)


def is_button_trigger(trigger: dict[str, Any]) -> bool:
    """Wahr, wenn dieser Geräteauslöser von einem Taster stammt."""
    kind = str(trigger.get("type") or "")
    if kind.startswith("remote_button"):
        return True
    if kind in _BUTTON_TYPES:
        return True
    return kind.endswith(_BUTTON_SUFFIXES)


def zone_from_name(name: str, zones: dict[str, str]) -> str | None:
    """Ordnet ein Bedienelement über seinen Namen einer Zone zu.

    Letzter Rückgriff, wenn dem Gerät kein Bereich zugewiesen ist: ein
    „Wandsender Flur" gehört offensichtlich in den Flur. Der längste
    passende Zonenname gewinnt, damit „Bad unten" vor „Bad oben" greift.
    """
    lowered = name.lower()
    treffer = [
        (zone_name, zone_id)
        for zone_id, zone_name in zones.items()
        if zone_name.lower() in lowered
    ]
    if not treffer:
        return None
    treffer.sort(key=lambda x: len(x[0]), reverse=True)
    return treffer[0][1]
