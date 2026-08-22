"""Tests des Prioritätsstapels — laufen ohne Home Assistant."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: E402

from lichtregie.core.stack import Claim, PriorityStack  # noqa: E402

LAYER_MANUAL = 60
LAYER_SCENE = 50
LAYER_PRESENCE = 40
LAYER_DAYLIGHT = 20
LAYER_BASE = 10


def stack_with(*claims: Claim, now: float = 0.0) -> PriorityStack:
    st = PriorityStack()
    for claim in claims:
        st.push(claim, now)
    return st


def test_highest_layer_wins():
    st = stack_with(
        Claim(layer=LAYER_PRESENCE, levels={"k1": 0.3}, source="Bewegung"),
        Claim(layer=LAYER_SCENE, levels={"k1": 0.8}, source="Szene"),
    )
    assert st.active.layer == LAYER_SCENE
    levels, _, _ = st.resolve()
    assert levels["k1"] == 0.8


def test_lower_layer_fills_untouched_circuits():
    """Eine Szene, die nur einen Kreis setzt, lässt die anderen unten stehen."""
    st = stack_with(
        Claim(layer=LAYER_DAYLIGHT, levels={"k1": 0.2, "k2": 0.2, "k3": 0.2}),
        Claim(layer=LAYER_SCENE, levels={"k2": 0.9}),
    )
    levels, _, _ = st.resolve()
    assert levels == {"k1": 0.2, "k2": 0.9, "k3": 0.2}
    assert st.covers("k2") == LAYER_SCENE
    assert st.covers("k1") == LAYER_DAYLIGHT
    assert st.covers("k9") is None


def test_manual_beats_scene_and_presence():
    """Der Fall aus dem Alltag: jemand dimmt von Hand."""
    st = stack_with(
        Claim(layer=LAYER_PRESENCE, levels={"k1": 0.3}),
        Claim(layer=LAYER_SCENE, levels={"k1": 0.8}),
        Claim(layer=LAYER_MANUAL, levels={"k1": 1.0}, source="Wandsender"),
    )
    assert st.active.layer == LAYER_MANUAL
    assert st.resolve()[0]["k1"] == 1.0


def test_expiry_falls_through():
    """Läuft die manuelle Ebene ab, übernimmt die Ebene darunter."""
    st = stack_with(
        Claim(layer=LAYER_PRESENCE, levels={"k1": 0.3}),
        Claim(layer=LAYER_MANUAL, levels={"k1": 1.0}, expires_at=100.0),
        now=0.0,
    )
    assert st.expire(now=99.0) == []
    assert st.active.layer == LAYER_MANUAL

    gone = st.expire(now=100.0)
    assert [c.layer for c in gone] == [LAYER_MANUAL]
    assert st.active.layer == LAYER_PRESENCE
    assert st.resolve()[0]["k1"] == 0.3


def test_no_expiry_when_none():
    st = stack_with(Claim(layer=LAYER_SCENE, levels={"k1": 0.5}, expires_at=None))
    assert st.expire(now=1e9) == []
    assert st.active is not None


def test_extend_resets_timer():
    """Erneute Bewegung setzt den Nachlauf zurück."""
    st = stack_with(
        Claim(layer=LAYER_PRESENCE, levels={"k1": 0.3}, expires_at=100.0), now=0.0
    )
    assert st.extend(LAYER_PRESENCE, seconds=180.0, now=90.0) is True
    assert st.expire(now=100.0) == []
    assert st.get(LAYER_PRESENCE).remaining(now=100.0) == 170.0
    assert st.extend(LAYER_SCENE, 60.0, now=0.0) is False


def test_release_above_clears_everything_but_base():
    """Langer Druck auf Aus: alle Ebenen oberhalb des Grundzustands frei."""
    st = stack_with(
        Claim(layer=LAYER_BASE, levels={"k1": 0.0}),
        Claim(layer=LAYER_PRESENCE, levels={"k1": 0.3}),
        Claim(layer=LAYER_SCENE, levels={"k1": 0.8}),
        Claim(layer=LAYER_MANUAL, levels={"k1": 1.0}),
    )
    gone = st.release_above(LAYER_BASE)
    assert sorted(c.layer for c in gone) == [
        LAYER_PRESENCE,
        LAYER_SCENE,
        LAYER_MANUAL,
    ]
    assert st.base_only()
    assert st.active.layer == LAYER_BASE


def test_push_replaces_same_layer():
    st = stack_with(Claim(layer=LAYER_SCENE, levels={"k1": 0.2}, source="alt"))
    st.push(Claim(layer=LAYER_SCENE, levels={"k1": 0.9}, source="neu"))
    assert len(st.layers) == 1
    assert st.active.source == "neu"


def test_snapshot_marks_active_layer():
    st = stack_with(
        Claim(layer=LAYER_PRESENCE, levels={"k1": 0.3}),
        Claim(layer=LAYER_MANUAL, levels={"k1": 1.0}, expires_at=7200.0, hold="2 h"),
    )
    snap = {row["layer"]: row for row in st.snapshot(now=0.0)}
    assert snap[LAYER_MANUAL]["active"] is True
    assert snap[LAYER_PRESENCE]["active"] is False
    assert snap[LAYER_PRESENCE]["claimed"] is True
    assert snap[LAYER_SCENE]["claimed"] is False
    assert snap[LAYER_MANUAL]["remaining"] == 7200.0


def test_store_and_restore_over_restart():
    """Nach einem Neustart steht der Raum wieder, wie er stand."""
    st = stack_with(
        Claim(layer=LAYER_SCENE, scene_id="entspannen", levels={"k1": 0.45},
              kelvin={"k1": 2400}, fade=3.0, source="Wandsender", hold="bis_leer"),
        Claim(layer=LAYER_MANUAL, levels={"k1": 1.0}, expires_at=7200.0,
              source="Hand", then="aus"),
        now=0.0,
    )
    saved = st.store(now=600.0)

    # Neuer Prozess: die monotone Uhr beginnt bei einem anderen Wert.
    again = PriorityStack()
    again.restore(saved, now=50_000.0)

    assert again.active.layer == LAYER_MANUAL
    assert again.active.then == "aus"
    # Restlaufzeit bleibt erhalten, nicht der absolute Zeitpunkt.
    assert again.get(LAYER_MANUAL).remaining(now=50_000.0) == 6600.0
    assert again.get(LAYER_SCENE).scene_id == "entspannen"
    assert again.get(LAYER_SCENE).kelvin == {"k1": 2400}
    assert again.get(LAYER_SCENE).remaining(now=50_000.0) is None


def test_restore_survives_broken_rows():
    """Eine kaputte Sicherung darf den Start nicht verhindern."""
    st = PriorityStack()
    st.restore(
        [{"layer": 50, "levels": {"k1": 0.5}}, {"kein_layer": True}, None],
        now=0.0,
    )
    assert st.layers == [50]


def test_restore_replaces_previous_content():
    st = stack_with(Claim(layer=LAYER_PRESENCE, levels={"k1": 0.3}))
    st.restore([{"layer": LAYER_SCENE, "levels": {"k2": 0.8}}], now=0.0)
    assert st.layers == [LAYER_SCENE]


def test_empty_stack():
    st = PriorityStack()
    assert st.active is None
    assert st.resolve()[0] == {}
    assert st.base_only() is True


if __name__ == "__main__":
    sys.exit(_bootstrap.run(globals()))
