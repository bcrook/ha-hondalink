from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .entity import HondaLinkEntity
from .util import get_path, status_body, to_int

PRESET_WINTER = "Winter Mode"
PRESET_SUMMER = "Summer Mode"
PRESET_OFF = "Climate Off"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([HondaLinkClimate(coordinator, entry)])


class HondaLinkClimate(HondaLinkEntity, ClimateEntity):
    """Climate entity for 2026 Honda Pilot."""

    _attr_has_entity_name = True
    _attr_name = "Climate"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE 
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = [PRESET_OFF, PRESET_WINTER, PRESET_SUMMER]
    _attr_min_temp = 16
    _attr_max_temp = 28
    _attr_target_temperature_step = 1

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "climate")

    @property
    def hvac_mode(self) -> HVACMode:
        body = status_body(self.coordinator.data or {})
        status = get_path(body, "remoteEngineStart.vehicleStartEvent.resStatus", "").upper()
        return HVACMode.HEAT_COOL if "RUN" in status else HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        body = status_body(self.coordinator.data or {})
        return to_int(get_path(body, "temperature.cabin.value"))

    @property
    def target_temperature(self) -> float | None:
        body = status_body(self.coordinator.data or {})
        return to_int(get_path(body, "remoteEngineStart.acStatus.acTempVal"))

    @property
    def preset_mode(self) -> str | None:
        body = status_body(self.coordinator.data or {})
        ac = get_path(body, "remoteEngineStart.acStatus", {})
        
        if ac.get("seatHeaterDrSetting") == "High Heat" and ac.get("strHeaterSetting") == "HSW ON":
            return PRESET_WINTER
        if ac.get("seatHeaterDrSetting") == "High Fan/Cooling" and ac.get("acTempVal") == "16":
            return PRESET_SUMMER
        return PRESET_OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.api.async_stop_engine()
        else:
            await self.coordinator.api.async_start_engine()
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.api.async_set_climate(temp=str(int(temp)))
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_WINTER:
            await self.coordinator.api.async_set_climate(
                temp="22",
                seat_dr="High Heat",
                seat_as="High Heat",
                wheel="HSW ON",
                defrost_f="MANUAL DEF ON",
                defrost_r="RRDEF ON"
            )
        elif preset_mode == PRESET_SUMMER:
            await self.coordinator.api.async_set_climate(
                temp="16",
                seat_dr="High Fan/Cooling",
                seat_as="High Fan/Cooling",
                wheel="HSW OFF",
                defrost_f="MANUAL DEF OFF",
                defrost_r="RRDEF OFF"
            )
        elif preset_mode == PRESET_OFF:
            await self.coordinator.api.async_set_climate(
                seat_dr="OFF",
                seat_as="OFF",
                wheel="HSW OFF",
                defrost_f="MANUAL DEF OFF",
                defrost_r="RRDEF OFF"
            )
        await self.coordinator.async_request_refresh()
