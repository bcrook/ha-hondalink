from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

_LOGGER = logging.getLogger(__name__)

def get_path(data: dict[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return default
        if cur is None:
            return default
    return cur


def status_body(data: dict[str, Any]) -> dict[str, Any]:
    """Extract the vehicle status body from the API response."""
    # Try the legacy NGT response wrapper
    body = data.get("responseBody")
    if isinstance(body, dict) and body:
        return body
    
    # For 2026+ Pilot (NGT), the payload might be at the top level
    # or inside a 'Body' key (seen in some APK samples)
    if "doorStatus" in data or "odometer" in data:
        return data
        
    body = data.get("Body")
    if isinstance(body, dict) and body:
        return body
        
    return data if isinstance(data, dict) else {}


def to_int(value: Any) -> int | None:
    try:
        if value in (None, "", "unknown"):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    try:
        if value in (None, "", "unknown"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def first_path(data: dict[str, Any], paths: tuple[str, ...]) -> Any:
    for path in paths:
        value = get_path(data, path)
        if value not in (None, "", "unknown"):
            return value
    return None


def value_from_status_node(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    for key in (
        "status",
        "state",
        "condition",
        "value",
        "text",
        "displayValue",
        "message",
        "messageText",
        "statusText",
        "displayText",
        "description",
    ):
        item = value.get(key)
        if item not in (None, "", "unknown"):
            return value_from_status_node(item)
    return None


def find_12v_battery_status(data: dict[str, Any]) -> Any:
    warning_lamp_status = _find_12v_warning_lamp_status(data)
    if warning_lamp_status not in (None, "", "unknown"):
        return warning_lamp_status

    direct = first_path(
        data,
        (
            "12VBatteryStatus",
            "12VBattery.status",
            "12VBattery.value",
            "twelveVoltBatteryStatus",
            "twelveVoltBattery.status",
            "twelveVoltBattery.value",
            "auxBatteryStatus",
            "auxBattery.status",
            "auxBattery.value",
            "auxiliaryBatteryStatus",
            "auxiliaryBattery.status",
            "auxiliaryBattery.value",
            "battery12VStatus",
            "battery12V.status",
            "battery12V.value",
            "batteryStatus12V",
            "batteryVoltageStatus",
            "batteryStatus.batteryVoltageStatus",
            "batteryStatus.batteryChargeStatus",
            "batteryStatus.status",
            "batteryStatus.value",
        ),
    )
    if direct not in (None, "", "unknown"):
        return value_from_status_node(direct)
    return "unknown"


def find_12v_battery_candidates(data: dict[str, Any]) -> dict[str, Any]:
    candidates: dict[str, Any] = {}
    _collect_12v_battery_candidates(data, "", candidates)
    return candidates


def leaf_paths(data: dict[str, Any], *, limit: int = 300) -> list[str]:
    paths: list[str] = []
    _collect_leaf_paths(data, "", paths, limit)
    return paths


def _find_12v_warning_lamp_status(data: dict[str, Any]) -> Any:
    for group in get_path(data, "warningLamps.data", []) or []:
        if not isinstance(group, dict):
            continue
        for message in group.get("messages", []) or []:
            if not isinstance(message, dict):
                continue
            text = " ".join(str(value) for value in message.values() if isinstance(value, str))
            text_lower = text.lower()
            has_12v = "12v" in text_lower or "12 v" in text_lower or "12 volt" in text_lower
            has_battery = "battery" in text_lower or "batt" in text_lower
            if has_12v and has_battery:
                return value_from_status_node(message)
    return None


def _collect_12v_battery_candidates(data: Any, path: str, candidates: dict[str, Any]) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key
            if "12v" in key.lower() or "battery" in key.lower():
                candidates[new_path] = value
            _collect_12v_battery_candidates(value, new_path, candidates)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            _collect_12v_battery_candidates(item, f"{path}[{index}]", candidates)


def _collect_leaf_paths(data: Any, path: str, paths: list[str], limit: int) -> None:
    if len(paths) >= limit:
        return
    if isinstance(data, dict):
        for key, value in data.items():
            _collect_leaf_paths(value, f"{path}.{key}" if path else key, paths, limit)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            _collect_leaf_paths(item, f"{path}[{index}]", paths, limit)
    else:
        paths.append(path)


def parse_iso_datetime(value: Any) -> datetime | None:
    if not value or value == "unknown":
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def dms_to_decimal(value: Any) -> float | None:
    if not value or value == "unknown":
        return None
    try:
        # Try DMS format (e.g., "043,49,56.945")
        str_val = str(value)
        if "," in str_val:
            parts = str_val.split(",")
            if len(parts) == 3:
                degrees = float(parts[0])
                sign = -1 if degrees < 0 else 1
                minutes = float(parts[1])
                seconds = float(parts[2])
                return sign * (abs(degrees) + minutes / 60 + seconds / 3600)
        
        # Fallback to standard decimal float for MY21 compatibility
        return float(value)
    except (TypeError, ValueError):
        return None


def any_open_state(body: dict[str, Any], base: str, keys: list[str], state_key: str = "openState") -> bool | None:
    found = False
    for key in keys:
        value = get_path(body, f"{base}.{key}.{state_key}")
        if value is not None:
            found = True
            if str(value).lower() != "closed":
                return True
    return False if found else None


def any_light_on(body: dict[str, Any]) -> bool | None:
    lights = get_path(body, "lightStatus", {})
    if not isinstance(lights, dict):
        return None
    found = False
    for item in lights.values():
        if isinstance(item, dict) and "lightState" in item:
            found = True
            if str(item.get("lightState")).upper() != "OFF":
                return True
    return False if found else None


def all_door_locks_locked(body: dict[str, Any]) -> bool | None:
    doors = get_path(body, "doorStatus", {})
    if not isinstance(doors, dict):
        return None
    states: list[str] = []
    for key in ("firstRowDriver", "firstRowPassenger", "secondRowDriver", "secondRowPassenger"):
        state = get_path(doors, f"{key}.lockState")
        if state:
            states.append(str(state))
    if not states:
        return None
    return all(state.lower() == "lock" for state in states)
