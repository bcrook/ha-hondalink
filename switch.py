from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .entity import HondaLinkEntity
from .util import get_path, status_body

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([
        HondaLinkClimateSwitch(coordinator, entry, "Heated Steering Wheel", "strHeaterSetting", "HSW ON", "HSW OFF"),
        HondaLinkClimateSwitch(coordinator, entry, "Front Defrost", "acDefFSetting", "MANUAL DEF ON", "MANUAL DEF OFF"),
        HondaLinkClimateSwitch(coordinator, entry, "Rear Defrost", "acDefRSetting", "RRDEF ON", "RRDEF OFF"),
    ])


class HondaLinkClimateSwitch(HondaLinkEntity, SwitchEntity):
    """Switch entity for Honda climate features."""

    def __init__(self, coordinator, entry: ConfigEntry, name: str, key: str, on_val: str, off_val: str) -> None:
        super().__init__(coordinator, entry, key)
        self._attr_name = name
        self._key = key
        self._on_val = on_val
        self._off_val = off_val

    @property
    def is_on(self) -> bool:
        body = status_body(self.coordinator.data or {})
        val = get_path(body, f"remoteEngineStart.acStatus.{self._key}")
        return val == self._on_val

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set_state(self._on_val)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_state(self._off_val)

    async def _async_set_state(self, value: str) -> None:
        body = status_body(self.coordinator.data or {})
        ac = get_path(body, "remoteEngineStart.acStatus", {})
        
        params = {
            "temp": ac.get("acTempVal"),
            "seat_dr": ac.get("seatHeaterDrSetting"),
            "seat_as": ac.get("seatHeaterAsSetting"),
            "wheel": ac.get("strHeaterSetting"),
            "defrost_f": ac.get("acDefFSetting"),
            "defrost_r": ac.get("acDefRSetting"),
        }
        
        # Update the specific key for this switch
        map_key = {
            "strHeaterSetting": "wheel",
            "acDefFSetting": "defrost_f",
            "acDefRSetting": "defrost_r",
        }[self._key]
        
        params[map_key] = value

        await self.coordinator.api.async_set_climate(**params)
        await self.coordinator.async_request_refresh()
