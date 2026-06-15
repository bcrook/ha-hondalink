from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .entity import HondaLinkEntity
from .util import get_path, status_body

SEAT_OPTIONS = [
    "OFF",
    "High Heat",
    "Medium Heat",
    "Low Heat",
    "High Fan/Cooling",
    "Medium Fan/Cooling",
    "Low Fan/Cooling",
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([
        HondaLinkSeatSelect(coordinator, entry, "Driver Seat", "seatHeaterDrSetting"),
        HondaLinkSeatSelect(coordinator, entry, "Passenger Seat", "seatHeaterAsSetting"),
    ])


class HondaLinkSeatSelect(HondaLinkEntity, SelectEntity):
    """Select entity for Honda seat settings."""

    _attr_options = SEAT_OPTIONS

    def __init__(self, coordinator, entry: ConfigEntry, name: str, key: str) -> None:
        super().__init__(coordinator, entry, key)
        self._attr_name = name
        self._key = key

    @property
    def current_option(self) -> str | None:
        body = status_body(self.coordinator.data or {})
        val = get_path(body, f"remoteEngineStart.acStatus.{self._key}")
        return val if val in SEAT_OPTIONS else "OFF"

    async def async_select_option(self, option: str) -> None:
        body = status_body(self.coordinator.data or {})
        ac = get_path(body, "remoteEngineStart.acStatus", {})
        
        params = {
            "temp": ac.get("acTempVal"),
            "wheel": ac.get("strHeaterSetting"),
            "defrost_f": ac.get("acDefFSetting"),
            "defrost_r": ac.get("acDefRSetting"),
        }
        
        if self._key == "seatHeaterDrSetting":
            params["seat_dr"] = option
            params["seat_as"] = ac.get("seatHeaterAsSetting")
        else:
            params["seat_dr"] = ac.get("seatHeaterDrSetting")
            params["seat_as"] = option

        await self.coordinator.api.async_set_climate(**params)
        await self.coordinator.async_request_refresh()
