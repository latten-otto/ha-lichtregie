"""Einrichtung.

Die Integration hat genau einen Eintrag; alles Weitere wird in der eigenen
Oberfläche eingestellt, nicht in Dialogen.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class LichtregieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ein Klick, dann geht es im Panel weiter."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

        return self.async_create_entry(title="Lichtregie", data={})
