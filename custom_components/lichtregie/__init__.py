"""Lichtregie — eigenständige Lichtsteuerung für Home Assistant.

Home Assistant liefert die Verbindung zu den Leuchten und Sensoren. Geplant,
geregelt und protokolliert wird in dieser Integration: eigene Engine, eigener
Prioritätsstapel, eigene Oberfläche. Es werden keine Automationen, Skripte,
Blueprints oder Szenen von Home Assistant benutzt.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import websocket as ws_api
from .const import DOMAIN, PANEL_ICON, PANEL_TITLE, PANEL_URL
from .core.journal import Journal
from .engine import Engine
from .store import ConfigStore, RuntimeStore

_LOGGER = logging.getLogger(__name__)

PANEL_PATH = "/lichtregie-static"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Startet die Integration."""
    store = ConfigStore(hass)
    installation = await store.load()

    journal = Journal()
    runtime_store = RuntimeStore(hass)
    engine = Engine(hass, installation, journal, runtime_store)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = {
        "store": store,
        "journal": journal,
        "engine": engine,
        "runtime_store": runtime_store,
        "entry": entry,
    }

    ws_api.async_register(hass)
    await _async_register_panel(hass)

    # Beim ersten Start die Anlage einlesen, damit das Panel nicht leer ist.
    if not installation.zones:
        from .link.discovery import discover

        try:
            found = await discover(hass)
            store.installation.zones = found.zones
            store.installation.controls = found.controls
            await store.save(label="Erstes Einlesen")
            _LOGGER.info(
                "Anlage eingelesen: %s Zonen, %s Bedienelemente",
                len(found.zones),
                len(found.controls),
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Anlage konnte nicht eingelesen werden: %s", err)

    await engine.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Hängt die eigene Oberfläche in die Seitenleiste."""
    panel_dir = Path(__file__).parent / "panel"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(PANEL_PATH, str(panel_dir), cache_headers=False)]
    )

    # "frontend_panels" ist der Schlüssel, unter dem das Frontend seine
    # registrierten Panels führt. Doppelt registrieren wirft einen Fehler.
    if PANEL_URL.lstrip("/") in hass.data.get("frontend_panels", {}):
        return

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="lichtregie-panel",
        frontend_url_path=PANEL_URL.lstrip("/"),
        module_url=f"{PANEL_PATH}/lichtregie-panel.js",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        config={},
    )


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Beendet die Integration."""
    data = hass.data.get(DOMAIN, {})
    engine: Engine | None = data.get("engine")
    if engine is not None:
        await engine.async_stop()
    frontend.async_remove_panel(
        hass, PANEL_URL.lstrip("/"), warn_if_unknown=False
    )
    hass.data.pop(DOMAIN, None)
    return True
