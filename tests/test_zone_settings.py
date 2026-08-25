"""Raumeinstellungen einer Zone — Richtwerte und Helligkeitssensor."""

from __future__ import annotations

import _bootstrap  # noqa: F401

from lichtregie.core.daylight import KIND_TO_CURVE
from lichtregie.core.model import Zone
from lichtregie.core.naming import KIND_DEFAULTS


def test_richtwerte_der_raumart_werden_uebernommen():
    zone = Zone(id="z1", name="Bad", kind="nassbereich")
    zone.setpoint_lux = 1.0
    zone.linger = 1.0
    assert zone.apply_kind_defaults() is True
    werte = KIND_DEFAULTS["nassbereich"]
    assert zone.setpoint_lux == werte["setpoint_lux"]
    assert zone.lux_on_below == werte["on_below"]
    assert zone.lux_off_above == werte["off_above"]
    assert zone.linger == werte["linger"]


def test_unbekannte_raumart_laesst_die_werte_stehen():
    zone = Zone(id="z1", name="Sauna", kind="dampfbad")
    zone.setpoint_lux = 77.0
    assert zone.apply_kind_defaults() is False
    assert zone.setpoint_lux == 77.0


def test_richtwerte_folgen_der_gewaehlten_raumart():
    zone = Zone(id="z1", name="Flur", kind="wohnraum")
    zone.kind = "verkehrsweg"
    zone.apply_kind_defaults()
    assert zone.linger == KIND_DEFAULTS["verkehrsweg"]["linger"]


def test_regelfaehiger_sensor_laesst_konstantlicht_bestehen():
    zone = Zone(id="z1", name="Büro", kind="arbeitsraum")
    zone.constant_light = True
    zone.use_lux_sensor("sensor.buero_lux", "regelfaehig")
    assert zone.lux_entity == "sensor.buero_lux"
    assert zone.lux_quality == "regelfaehig"
    assert zone.constant_light is True


def test_untauglicher_sensor_schaltet_konstantlicht_ab():
    zone = Zone(id="z1", name="Büro", kind="arbeitsraum")
    zone.constant_light = True
    zone.use_lux_sensor("sensor.melder_lux", "momentaufnahme")
    assert zone.constant_light is False


def test_sensor_entfernen_setzt_die_einstufung_zurueck():
    zone = Zone(id="z1", name="Büro", kind="arbeitsraum")
    zone.use_lux_sensor("sensor.buero_lux", "regelfaehig")
    zone.constant_light = True
    zone.use_lux_sensor("")
    assert zone.lux_entity is None
    assert zone.lux_quality == "unbekannt"
    assert zone.constant_light is False


def test_sensorwechsel_ueberlebt_speichern_und_laden():
    zone = Zone(id="z1", name="Bad", kind="nassbereich")
    zone.presence_entities = ["binary_sensor.bad_bewegung"]
    zone.use_lux_sensor("sensor.bad_lux", "regelfaehig")
    zurueck = Zone.from_dict(zone.to_dict())
    assert zurueck.presence_entities == ["binary_sensor.bad_bewegung"]
    assert zurueck.lux_entity == "sensor.bad_lux"
    assert zurueck.lux_quality == "regelfaehig"


def test_jede_raumart_hat_eine_kurve():
    # Die Oberfläche zeigt „aus der Raumart (…)" — ohne Zuordnung stünde
    # dort ein leerer Klammerausdruck.
    for kind in KIND_DEFAULTS:
        assert KIND_TO_CURVE.get(kind), f"{kind} ohne Kurve"


if __name__ == "__main__":
    import sys

    sys.exit(_bootstrap.run(dict(globals())))
