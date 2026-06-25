from __future__ import annotations

import logging
import uuid

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import HondaLinkAPI
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_REG_KEY,
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_DISABLE_REDACTION,
    CONF_EMAIL,

    CONF_EXPIRES_AT,
    CONF_HIDAS_IDENT,
    CONF_LANGUAGE,
    CONF_LOCK_COMMAND,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_REFRESH_TOKEN,
    CONF_SESSION_ID,
    CONF_UNLOCK_COMMAND,
    CONF_VIN,
    DATA_API,
    DATA_COORDINATOR,
    DEFAULT_LOCK_COMMAND,
    DEFAULT_UNLOCK_COMMAND,
    DOMAIN,
)
from .coordinator import HondaLinkDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    # Register services early
    async def handle_set_climate(call: ServiceCall):
        """Handle the set_climate service call."""
        if entry.entry_id not in hass.data[DOMAIN]:
            _LOGGER.error("HondaLink integration not ready for service call")
            return

        coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        await coordinator.api.async_set_climate(
            temp=call.data.get("temp"),
            seat_dr=call.data.get("seat_dr"),
            seat_as=call.data.get("seat_as"),
            wheel=call.data.get("wheel"),
            defrost_f=call.data.get("defrost_f"),
            defrost_r=call.data.get("defrost_r"),
        )

    if not hass.services.has_service(DOMAIN, "set_climate"):
        _LOGGER.debug("Registering HondaLink set_climate service")
        hass.services.async_register(DOMAIN, "set_climate", handle_set_climate)

    data = dict(entry.data)
    changed = False
    if not data.get(CONF_DEVICE_ID):
        data[CONF_DEVICE_ID] = str(uuid.uuid4())
        changed = True
    if not data.get(CONF_SESSION_ID):
        data[CONF_SESSION_ID] = str(uuid.uuid4())
        changed = True
    if changed:
        hass.config_entries.async_update_entry(entry, data=data)

    session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar())
    api = HondaLinkAPI(
        session,
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        pin=entry.options.get(CONF_PIN, data.get(CONF_PIN)),
        vin=data[CONF_VIN],
        client_reg_key=data.get(CONF_CLIENT_REG_KEY),
        access_token=data.get(CONF_ACCESS_TOKEN),
        refresh_token=data.get(CONF_REFRESH_TOKEN),
        expires_at=data.get(CONF_EXPIRES_AT),
        country=data.get(CONF_COUNTRY, "US"),
        language=data.get(CONF_LANGUAGE, "en"),
        hidas_ident=data.get(CONF_HIDAS_IDENT),
        device_id=data[CONF_DEVICE_ID],
        session_id=data[CONF_SESSION_ID],
        lock_command=entry.options.get(CONF_LOCK_COMMAND, DEFAULT_LOCK_COMMAND),
        unlock_command=entry.options.get(CONF_UNLOCK_COMMAND, DEFAULT_UNLOCK_COMMAND),
        disable_redaction=entry.options.get(CONF_DISABLE_REDACTION, False),
    )
    await api.async_ensure_login()

    auth_data = api.export_auth_data()
    if any(data.get(key) != value for key, value in auth_data.items()):
        hass.config_entries.async_update_entry(entry, data={**data, **auth_data})

    coordinator = HondaLinkDataUpdateCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_API: api,
        DATA_COORDINATOR: coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

