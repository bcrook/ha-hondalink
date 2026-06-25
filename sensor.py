from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .entity import HondaLinkEntity
from .util import (
    find_12v_battery_candidates,
    find_12v_battery_status,
    get_path,
    leaf_paths,
    parse_iso_datetime,
    status_body,
    to_float,
    to_int,
)


@dataclass(frozen=True, kw_only=True)
class HondaLinkSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    attr_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    unit_fn: Callable[[dict[str, Any]], str | None] | None = None


def _parse_length_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = str(unit).lower()
    if u in ("km", "kilometers", "kilometer"):
        return UnitOfLength.KILOMETERS
    if u in ("mi", "miles", "mile"):
        return UnitOfLength.MILES
    return unit


def _parse_speed_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = str(unit).lower()
    if u in ("km/h", "kmh"):
        return UnitOfSpeed.KILOMETERS_PER_HOUR
    if u in ("mph", "mi/h"):
        return UnitOfSpeed.MILES_PER_HOUR
    return unit


def _parse_pressure_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = str(unit).lower()
    if u == "kpa":
        return UnitOfPressure.KPA
    if u == "psi":
        return UnitOfPressure.PSI
    if u == "bar":
        return UnitOfPressure.BAR
    return unit


def _parse_temperature_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = str(unit).lower()
    if u == "c":
        return UnitOfTemperature.CELSIUS
    if u == "f":
        return UnitOfTemperature.FAHRENHEIT
    return unit


def _tire(path: str):
    def _value_fn(body: dict[str, Any]) -> int | None:
        val = to_int(get_path(body, f"tireStatus.{path}.pressureData.value"))
        return None if val == 510 else val

    return _value_fn


def _cabin_temp(body: dict[str, Any]) -> float | None:
    val = get_path(body, "temperature.cabin.value")
    if val in (None, "unknown", "Not Used"):
        return None
    return to_float(val)


def _tire_unit(path: str):
    def _unit_fn(body: dict[str, Any]) -> str | None:
        return _parse_pressure_unit(get_path(body, f"tireStatus.{path}.pressureData.unit"))

    return _unit_fn


SENSORS: tuple[HondaLinkSensorDescription, ...] = (
    HondaLinkSensorDescription(
        key="cabin_temperature",
        name="Cabin Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_cabin_temp,
        unit_fn=lambda body: _parse_temperature_unit(get_path(body, "temperature.cabin.unit")),
    ),
    HondaLinkSensorDescription(
        key="fuel_level",
        translation_key="fuel_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda body: to_int(get_path(body, "fuelLevel.currentLevel.value")),
    ),
    HondaLinkSensorDescription(
        key="range",
        translation_key="range",
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda body: to_int(get_path(body, "fuelLevel.driveRange.value")),
        unit_fn=lambda body: _parse_length_unit(get_path(body, "fuelLevel.driveRange.unit")),
    ),
    HondaLinkSensorDescription(
        key="odometer",
        translation_key="odometer",
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda body: to_int(get_path(body, "odometer.value")),
        unit_fn=lambda body: _parse_length_unit(get_path(body, "odometer.unit")),
    ),
    HondaLinkSensorDescription(
        key="oil_life",
        translation_key="oil_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda body: to_int(get_path(body, "oilLife.value")),
    ),
    HondaLinkSensorDescription(
        key="12v_battery_status",
        translation_key="12v_battery_status",
        value_fn=find_12v_battery_status,
        attr_fn=lambda body: {
            "battery_candidates": find_12v_battery_candidates(body),
            "dashboard_keys": sorted(body.keys()),
            "dashboard_leaf_paths": leaf_paths(body),
        },
    ),
    HondaLinkSensorDescription(
        key="front_left_tire_pressure",
        translation_key="front_left_tire_pressure",
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_tire("frontLeft"),
        unit_fn=_tire_unit("frontLeft"),
    ),
    HondaLinkSensorDescription(
        key="front_right_tire_pressure",
        translation_key="front_right_tire_pressure",
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_tire("frontRight"),
        unit_fn=_tire_unit("frontRight"),
    ),
    HondaLinkSensorDescription(
        key="rear_left_tire_pressure",
        translation_key="rear_left_tire_pressure",
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_tire("rearLeft"),
        unit_fn=_tire_unit("rearLeft"),
    ),
    HondaLinkSensorDescription(
        key="rear_right_tire_pressure",
        translation_key="rear_right_tire_pressure",
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_tire("rearRight"),
        unit_fn=_tire_unit("rearRight"),
    ),
    HondaLinkSensorDescription(
        key="vehicle_speed",
        translation_key="vehicle_speed",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda body: to_float(get_path(body, "gpsData.velocity.value")),
        unit_fn=lambda body: _parse_speed_unit(get_path(body, "gpsData.velocity.unit")),
    ),
    HondaLinkSensorDescription(
        key="remote_engine_status",
        translation_key="remote_engine_status",
        value_fn=lambda body: get_path(body, "remoteEngineStart.vehicleStartEvent.resStatus"),
    ),
    HondaLinkSensorDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda body: parse_iso_datetime(get_path(body, "timestamp")),
    ),
    HondaLinkSensorDescription(
        key="raw_vehicle_status",
        name="Raw Vehicle Status",
        icon="mdi:json",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda body: get_path(body, "timestamp"),
        attr_fn=lambda body: {"data": body},
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(HondaLinkSensor(coordinator, entry, description) for description in SENSORS)


class HondaLinkSensor(HondaLinkEntity, SensorEntity):
    entity_description: HondaLinkSensorDescription

    def __init__(self, coordinator, entry: ConfigEntry, description: HondaLinkSensorDescription) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def icon(self) -> str | None:
        if self.entity_description.key == "fuel_level":
            body = status_body(self.coordinator.data or {})
            ev_soc = get_path(body, "evStatus.vehicleInfo.soc.value")
            if ev_soc in (None, "unknown"):
                return "mdi:gas-station"
            return "mdi:battery"
        return self.entity_description.icon

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.unit_fn is not None:
            if unit := self.entity_description.unit_fn(status_body(self.coordinator.data or {})):
                return unit
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(status_body(self.coordinator.data or {}))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attr_fn is None:
            return None
        attrs = self.entity_description.attr_fn(status_body(self.coordinator.data or {}))
        if self.entity_description.key == "raw_vehicle_status" and hasattr(self.coordinator, "last_response_headers"):
            attrs = dict(attrs) if attrs else {}
            headers = dict(self.coordinator.last_response_headers)
            disable_redaction = getattr(self.coordinator.api, "disable_redaction", False)
            if not disable_redaction:
                for key in list(headers.keys()):
                    if key.lower() in ("set-cookie", "cookie", "authorization", "proxy-authorization"):
                        headers[key] = "**REDACTED**"
            attrs["headers"] = headers
        return attrs
