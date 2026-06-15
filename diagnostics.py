from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_DISABLE_REDACTION, DATA_COORDINATOR, DOMAIN
from .coordinator import HondaLinkDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: HondaLinkDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    disable_redaction = entry.options.get(CONF_DISABLE_REDACTION, False)

    if disable_redaction:
        entry_data = dict(entry.data)
    else:
        entry_data = {
            k: v
            for k, v in entry.data.items()
            if k not in ["password", "access_token", "refresh_token", "client_reg_key", "pin"]
        }

    raw_vehicle_data = coordinator.data

    return {
        "entry": {
            "data": entry_data,
            "options": dict(entry.options),
        },
        "raw_vehicle_data": raw_vehicle_data,
    }


