"""Datenmodell der Anlage.

Vier Ebenen: Anlage → Zone → Lichtkreis → Leuchte. Dazu Szenen, Bindungen
und Bedienelemente. Alle Objekte sind reine Daten und lassen sich
verlustfrei in JSON und zurück wandeln.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..const import (
    DEFAULT_CURVE,
    HOLD_WHILE_OCCUPIED,
    LAYER_SCENE,
    ROLE_GENERAL,
)
from .naming import KIND_DEFAULTS


def _new_id(prefix: str, taken: set[str]) -> str:
    i = 1
    while f"{prefix}{i}" in taken:
        i += 1
    return f"{prefix}{i}"


# --------------------------------------------------------------------------
# Ebene 4 — Leuchte
# --------------------------------------------------------------------------


@dataclass
class Fixture:
    """Ein physisches Leuchtmittel, genau eine Entität in Home Assistant."""

    entity_id: str
    name: str = ""

    # Fähigkeiten, beim Einlesen ermittelt
    dimmable: bool = True
    color_temp: bool = False
    color: bool = False
    min_kelvin: int | None = None
    max_kelvin: int | None = None
    supports_transition: bool = True

    # Betriebsgrenzen und Kurve
    curve: str = DEFAULT_CURVE
    min_flux: float = 0.01
    max_flux: float = 1.0

    # Eigenschaften für Regeln
    glares: bool = False
    night_capable: bool = False
    # Ob die Software die Farbtemperatur führen darf. Kann die Leuchte es
    # nicht, ist es ohnehin aus; kann sie es, will man es trotzdem nicht
    # immer — manche Leuchten sollen ihre eingestellte Farbe behalten.
    manage_color: bool = True

    # Messwerte. Der Lux-Beitrag steht nicht hier, sondern in der
    # Kalibrierung der Zone — dort wird je Lichtkreis gemessen, und ein
    # zweiter Ort für dieselbe Größe wäre eine zweite Wahrheit.
    watts: float | None = None
    hours: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Fixture:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


# --------------------------------------------------------------------------
# Ebene 3 — Lichtkreis
# --------------------------------------------------------------------------


@dataclass
class Circuit:
    """Leuchten, die immer gemeinsam denselben Wert bekommen.

    Ein Kreis kann mehrere Aufgaben haben: eine Dekolampe ist tagsüber
    Akzentlicht und nachts Orientierung. Die erste Rolle gilt als die
    hauptsächliche und bestimmt Symbol und Sortierung.
    """

    id: str
    name: str
    roles: list[str] = field(default_factory=lambda: [ROLE_GENERAL])
    fixtures: list[Fixture] = field(default_factory=list)
    enabled: bool = True
    icon: str = ""

    def __post_init__(self) -> None:
        # Eine einzelne Rolle als Zeichenkette annehmen: sonst würde sie als
        # Zeichenliste behandelt und jede Prüfung stillschweigend falsch.
        if isinstance(self.roles, str):
            self.roles = [self.roles]
        if not self.roles:
            self.roles = [ROLE_GENERAL]

    @property
    def role(self) -> str:
        """Die hauptsächliche Aufgabe."""
        return self.roles[0] if self.roles else ROLE_GENERAL

    @role.setter
    def role(self, value: str) -> None:
        """Setzt die Hauptrolle, ohne die übrigen zu verlieren."""
        self.roles = [value] + [r for r in self.roles if r != value]

    def has_role(self, role: str) -> bool:
        return role in self.roles

    @property
    def entity_ids(self) -> list[str]:
        return [f.entity_id for f in self.fixtures]

    @property
    def glares(self) -> bool:
        return any(f.glares for f in self.fixtures)

    @property
    def night_capable(self) -> bool:
        return all(f.night_capable for f in self.fixtures) and bool(self.fixtures)

    @property
    def color_temp(self) -> bool:
        return any(f.color_temp or f.color for f in self.fixtures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "roles": list(self.roles),
            # Für ältere Leser und die Anzeige weiterhin die Hauptrolle.
            "role": self.role,
            "icon": self.icon,
            "enabled": self.enabled,
            "fixtures": [f.to_dict() for f in self.fixtures],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Circuit:
        rollen = data.get("roles")
        if not rollen:
            rollen = [data.get("role", ROLE_GENERAL)]
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            roles=[r for r in rollen if r] or [ROLE_GENERAL],
            icon=data.get("icon", ""),
            enabled=data.get("enabled", True),
            fixtures=[Fixture.from_dict(f) for f in data.get("fixtures", [])],
        )


# --------------------------------------------------------------------------
# Szenen und Bindungen
# --------------------------------------------------------------------------


@dataclass
class SceneStep:
    """Sollwert eines Kreises — nur noch für das Einlesen alter Fassungen."""

    circuit_id: str
    level: float = 0.0
    kelvin: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SceneStep:
        return cls(
            circuit_id=data["circuit_id"],
            level=float(data.get("level", 0.0)),
            kelvin=data.get("kelvin"),
        )


@dataclass
class Scene:
    """Eine gespeicherte Lichtstimmung einer Zone.

    Eine Szene wird in Ebenen gedacht, nicht in Leuchten: „Stimmung auf
    45 %, Deckenlicht auf 15 %". Dadurch bleibt sie gültig, wenn eine
    Leuchte dazukommt oder wegfällt — sie erbt den Wert ihrer Rolle.

    ``overrides`` hält die Ausnahmen: einzelne Lichtkreise, die von ihrem
    Rollenwert abweichen sollen. Ein Wert von 0 nimmt den Kreis aus der
    Szene heraus, obwohl seine Rolle leuchtet.
    """

    id: str
    name: str
    levels: dict[str, float] = field(default_factory=dict)  # je Rolle
    overrides: dict[str, float] = field(default_factory=dict)  # je Lichtkreis
    kelvin: int | None = None
    fade: float = 1.5
    follows_daylight: bool = False
    max_lux: float | None = None
    min_state: str | None = None

    def level_for(self, circuit: "Circuit") -> float:
        """Sollwert eines Lichtkreises in dieser Szene.

        Die Ausnahme schlägt die Rolle. Hat ein Kreis mehrere Rollen,
        gilt die hellste — sonst würde eine Leuchte, die Akzent und
        Orientierung ist, in der Akzentszene auf Nachtniveau laufen.
        """
        if circuit.id in self.overrides:
            return self.overrides[circuit.id]
        werte = [self.levels.get(rolle, 0.0) for rolle in circuit.roles]
        return max(werte) if werte else 0.0

    def resolve(self, zone: "Zone") -> dict[str, float]:
        """Alle Sollwerte der Zone in dieser Szene."""
        return {
            c.id: self.level_for(c)
            for c in zone.circuits
            if c.enabled and self.level_for(c) > 0
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "levels": dict(self.levels),
            "overrides": dict(self.overrides),
            "kelvin": self.kelvin,
            "fade": self.fade,
            "follows_daylight": self.follows_daylight,
            "max_lux": self.max_lux,
            "min_state": self.min_state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scene:
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            levels={k: float(v) for k, v in (data.get("levels") or {}).items()},
            overrides={k: float(v) for k, v in (data.get("overrides") or {}).items()},
            kelvin=data.get("kelvin"),
            fade=float(data.get("fade", 1.5)),
            follows_daylight=data.get("follows_daylight", False),
            max_lux=data.get("max_lux"),
            min_state=data.get("min_state"),
        )


@dataclass
class Binding:
    """Verbindet einen Auslöser mit einer Szene.

    Fünf Teile: Auslöser, Bedingung, Ebene, Haltedauer, Danach.
    """

    id: str
    trigger: dict[str, Any] = field(default_factory=dict)
    scene_id: str | None = None
    action: str = "scene"  # scene · off · automatik · weiter · dimmen · zone_aus
    layer: int = LAYER_SCENE
    hold: str = HOLD_WHILE_OCCUPIED
    hold_seconds: float | None = None
    until: str | None = None  # für hold=bis_zeitpunkt
    then: str = "automatik"  # automatik · vorherige · aus · grundzustand
    conditions: dict[str, Any] = field(default_factory=dict)
    zones: list[str] = field(default_factory=list)  # leer = eigene Zone
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Binding:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


# --------------------------------------------------------------------------
# Bedienelemente
# --------------------------------------------------------------------------


@dataclass
class ControlPoint:
    """Ein Taster, Wandsender oder Eingang — herstellerunabhängig.

    ``source`` sagt, aus welcher Welt die Ereignisse kommen:
    ``device_trigger`` (deCONZ, ZHA), ``event_entity`` (Shelly, moderne
    Integrationen) oder ``binary_sensor`` (reiner Kontakt).
    """

    id: str
    name: str
    source: str
    device_id: str | None = None
    entity_id: str | None = None
    zone_id: str | None = None
    model: str = ""
    buttons: int = 1
    bindings: list[Binding] = field(default_factory=list)
    # Zigbee-Direktbindungen, die an Home Assistant vorbei schalten
    direct_bound: bool = False
    direct_groups: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["bindings"] = [b.to_dict() for b in self.bindings]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ControlPoint:
        known = {f for f in cls.__dataclass_fields__ if f != "bindings"}
        obj = cls(**{k: v for k, v in data.items() if k in known})
        obj.bindings = [Binding.from_dict(b) for b in data.get("bindings", [])]
        return obj


# --------------------------------------------------------------------------
# Ebene 2 — Zone
# --------------------------------------------------------------------------


@dataclass
class Zone:
    """Ein Regelbereich, meist ein Raum."""

    id: str
    name: str
    kind: str = "wohnraum"
    area_id: str | None = None

    circuits: list[Circuit] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    bindings: list[Binding] = field(default_factory=list)

    # Sensorik
    presence_entities: list[str] = field(default_factory=list)
    lux_entity: str | None = None
    lux_quality: str = "unbekannt"  # regelfaehig · momentaufnahme · tot
    door_entities: list[str] = field(default_factory=list)
    media_entities: list[str] = field(default_factory=list)

    # Regelwerte
    setpoint_lux: float = 150.0
    lux_on_below: float = 200.0
    lux_off_above: float = 260.0
    linger: float = 300.0  # Nachlauf in Sekunden
    extended_after: float = 900.0
    warn_before: float = 30.0
    warn_level: float = 0.3
    night_start: str = "23:00"
    night_end: str = "sunrise"
    enabled: bool = True

    # Tagesverlauf und Konstantlichtregelung
    curve_key: str = ""          # leer heißt: aus dem Raumtyp ableiten
    daylight: bool = True        # Farbe und Helligkeit nachführen
    constant_light: bool = False # nur sinnvoll bei regelfähigem Sensor
    calibration: dict = field(default_factory=dict)

    def apply_kind_defaults(self) -> bool:
        """Übernimmt die Richtwerte der Raumart.

        Ausdrücklich und nur auf Verlangen: eine von Hand eingestellte Zone
        verlöre sonst bei jedem Wechsel der Raumart ihre Werte. Gibt zurück,
        ob es für die Art überhaupt Richtwerte gibt.
        """
        werte = KIND_DEFAULTS.get(self.kind)
        if not werte:
            return False
        self.setpoint_lux = float(werte["setpoint_lux"])
        self.lux_on_below = float(werte["on_below"])
        self.lux_off_above = float(werte["off_above"])
        self.linger = float(werte["linger"])
        return True

    def use_lux_sensor(self, entity_id: str | None, quality: str = "unbekannt") -> None:
        """Setzt den Helligkeitssensor und zieht die Folgen daraus.

        Konstantlichtregelung braucht einen Sensor, der Änderungen zeigt.
        Fällt der Sensor weg oder taugt der neue nur für Momentaufnahmen,
        wird sie abgeschaltet — sonst regelte die Zone gegen einen Wert,
        der sich nie bewegt, und pumpte.
        """
        self.lux_entity = entity_id or None
        self.lux_quality = quality if self.lux_entity else "unbekannt"
        if self.lux_quality != "regelfaehig":
            self.constant_light = False

    def circuit(self, circuit_id: str) -> Circuit | None:
        return next((c for c in self.circuits if c.id == circuit_id), None)

    def scene(self, scene_id: str) -> Scene | None:
        return next((s for s in self.scenes if s.id == scene_id), None)

    def circuits_with_role(self, role: str) -> list[Circuit]:
        return [c for c in self.circuits if c.has_role(role) and c.enabled]

    @property
    def roles(self) -> set[str]:
        return {r for c in self.circuits if c.enabled for r in c.roles}

    @property
    def entity_ids(self) -> list[str]:
        return [e for c in self.circuits for e in c.entity_ids]

    def new_circuit_id(self) -> str:
        return _new_id("k", {c.id for c in self.circuits})

    def new_scene_id(self) -> str:
        return _new_id("s", {s.id for s in self.scenes})

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "area_id": self.area_id,
            "enabled": self.enabled,
            "presence_entities": self.presence_entities,
            "lux_entity": self.lux_entity,
            "lux_quality": self.lux_quality,
            "door_entities": self.door_entities,
            "media_entities": self.media_entities,
            "setpoint_lux": self.setpoint_lux,
            "lux_on_below": self.lux_on_below,
            "lux_off_above": self.lux_off_above,
            "linger": self.linger,
            "extended_after": self.extended_after,
            "warn_before": self.warn_before,
            "warn_level": self.warn_level,
            "night_start": self.night_start,
            "night_end": self.night_end,
            "curve_key": self.curve_key,
            "daylight": self.daylight,
            "constant_light": self.constant_light,
            "calibration": self.calibration,
            "circuits": [c.to_dict() for c in self.circuits],
            "scenes": [s.to_dict() for s in self.scenes],
            "bindings": [b.to_dict() for b in self.bindings],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Zone:
        known = {
            f
            for f in cls.__dataclass_fields__
            if f not in ("circuits", "scenes", "bindings")
        }
        zone = cls(**{k: v for k, v in data.items() if k in known})
        zone.circuits = [Circuit.from_dict(c) for c in data.get("circuits", [])]
        zone.scenes = [Scene.from_dict(s) for s in data.get("scenes", [])]
        zone.bindings = [Binding.from_dict(b) for b in data.get("bindings", [])]
        return zone


# --------------------------------------------------------------------------
# Ebene 1 — Anlage
# --------------------------------------------------------------------------


@dataclass
class Installation:
    """Die gesamte Anlage."""

    zones: list[Zone] = field(default_factory=list)
    controls: list[ControlPoint] = field(default_factory=list)
    mode: str = "normal"  # normal · abwesend · urlaub · gaeste · wartung
    version: int = 1

    def zone(self, zone_id: str) -> Zone | None:
        return next((z for z in self.zones if z.id == zone_id), None)

    def control(self, control_id: str) -> ControlPoint | None:
        return next((c for c in self.controls if c.id == control_id), None)

    def zone_of_entity(self, entity_id: str) -> Zone | None:
        for zone in self.zones:
            if entity_id in zone.entity_ids:
                return zone
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "mode": self.mode,
            "zones": [z.to_dict() for z in self.zones],
            "controls": [c.to_dict() for c in self.controls],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Installation:
        return cls(
            version=data.get("version", 1),
            mode=data.get("mode", "normal"),
            zones=[Zone.from_dict(z) for z in data.get("zones", [])],
            controls=[ControlPoint.from_dict(c) for c in data.get("controls", [])],
        )
