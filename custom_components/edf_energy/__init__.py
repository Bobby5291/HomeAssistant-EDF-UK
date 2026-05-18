# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging
from datetime import timedelta

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers import device_registry as dr
from homeassistant.util.dt import utcnow
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from .api_client import ApiException, AuthenticationException, EDFEnergyApiClient
from .coordinators.account import AccountCoordinatorResult, async_setup_account_info_coordinator
from .coordinators.electricity_rates import async_setup_electricity_rates_coordinator
from .coordinators.electricity_standing_charges import async_setup_electricity_standing_charges_coordinator
from .coordinators.current_consumption import async_create_current_consumption_coordinator
from .coordinators.previous_consumption_and_rates import async_create_previous_consumption_and_rates_coordinator

from .utils import get_active_tariff, get_tariff_parts
from .utils.error import api_exception_to_string
from .storage.account import async_load_cached_account, async_save_cached_account

from .const import (
    CONFIG_ACCOUNT_ID,
    CONFIG_MAIN_EMAIL,
    CONFIG_MAIN_PASSWORD,
    CONFIG_MAIN_SUPPORTS_LIVE_CONSUMPTION,
    CONFIG_MAIN_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
    CONFIG_DEFAULT_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
    CONFIG_VERSION,
    DATA_CLIENT,
    DATA_ACCOUNT,
    DATA_ACCOUNT_COORDINATOR,
    DATA_ELECTRICITY_RATES_COORDINATOR_KEY,
    DATA_CURRENT_CONSUMPTION_KEY,
    DOMAIN,
    REPAIR_ACCOUNT_NOT_FOUND,
    REPAIR_INVALID_CREDENTIALS,
)

_LOGGER = logging.getLogger(__name__)

ACCOUNT_PLATFORMS = ["sensor", "binary_sensor", "event"]


async def async_remove_config_entry_device(hass, config_entry, device_entry) -> bool:
    """Allow removal of devices from the UI."""
    return True


async def async_migrate_entry(hass, config_entry):
    """Migrate old config entries to current version."""
    if config_entry.version < CONFIG_VERSION:
        _LOGGER.debug("Migrating from version %s", config_entry.version)
        new_data = dict(config_entry.data)
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            options={},
            version=CONFIG_VERSION,
        )
        _LOGGER.debug("Migration to version %s successful", CONFIG_VERSION)
    return True


async def _async_close_client(hass, account_id: str):
    """Close the aiohttp session on the API client."""
    if account_id in hass.data[DOMAIN]:
        if DATA_CLIENT in hass.data[DOMAIN][account_id]:
            client: EDFEnergyApiClient = hass.data[DOMAIN][account_id][DATA_CLIENT]
            await client.async_close()
            _LOGGER.debug("EDF API client closed.")


async def async_setup_entry(hass, entry):
    """Called by HA when the integration config entry is loaded."""
    hass.data.setdefault(DOMAIN, {})

    config = dict(entry.data)
    account_id = config[CONFIG_ACCOUNT_ID]
    hass.data[DOMAIN].setdefault(account_id, {})

    await async_setup_dependencies(hass, config)
    await hass.config_entries.async_forward_entry_setups(entry, ACCOUNT_PLATFORMS)

    async def async_close_connection(_) -> None:
        await _async_close_client(hass, account_id)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    return True


async def options_update_listener(hass, entry):
    """Reload the entry when options are updated (e.g. reconfigure)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    """Unload the config entry and clean up."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ACCOUNT_PLATFORMS)

    if unload_ok:
        account_id = entry.data[CONFIG_ACCOUNT_ID]
        await _async_close_client(hass, account_id)
        hass.data[DOMAIN].pop(account_id, None)

    return unload_ok


async def async_setup_dependencies(hass, config):
    """
    Core setup — runs on every load/reload.
    Creates the API client, fetches account info, then sets up all coordinators.
    """
    account_id = config[CONFIG_ACCOUNT_ID]

    # Clear any stale repair issues from previous runs
    ir.async_delete_issue(hass, DOMAIN, REPAIR_ACCOUNT_NOT_FOUND.format(account_id))
    ir.async_delete_issue(hass, DOMAIN, REPAIR_INVALID_CREDENTIALS.format(account_id))

    # Close any existing client session before creating a new one
    await _async_close_client(hass, account_id)

    client = EDFEnergyApiClient(
        email=config[CONFIG_MAIN_EMAIL],
        password=config[CONFIG_MAIN_PASSWORD],
    )
    hass.data[DOMAIN][account_id][DATA_CLIENT] = client

    # -------------------------------------------------------------------------
    # Fetch account info — fall back to cache if API is unavailable on startup
    # -------------------------------------------------------------------------
    try:
        account_info = await client.async_get_account(account_id)

        if account_info is None:
            raise ConfigEntryNotReady("Failed to retrieve account information from EDF")

        await async_save_cached_account(hass, account_id, account_info)
        ir.async_delete_issue(hass, DOMAIN, REPAIR_ACCOUNT_NOT_FOUND.format(account_id))
        ir.async_delete_issue(hass, DOMAIN, REPAIR_INVALID_CREDENTIALS.format(account_id))

    except Exception as e:
        if not isinstance(e, ApiException):
            raise

        if isinstance(e, AuthenticationException):
            ir.async_create_issue(
                hass,
                DOMAIN,
                REPAIR_INVALID_CREDENTIALS.format(account_id),
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="invalid_credentials",
                translation_placeholders={"account_id": account_id},
            )
            raise ConfigEntryNotReady(
                f"EDF authentication failed: {api_exception_to_string(e)}"
            )
        else:
            account_info = await async_load_cached_account(hass, account_id)
            if account_info is None:
                raise ConfigEntryNotReady(
                    f"Failed to retrieve EDF account info and no cache available: {api_exception_to_string(e)}"
                )
            _LOGGER.warning(
                f"Using cached account information for {account_id} — will retry automatically."
            )

    # Store initial account result so coordinators have something to read immediately
    hass.data[DOMAIN][account_id][DATA_ACCOUNT] = AccountCoordinatorResult(
        utcnow(), 1, account_info
    )

    now = utcnow()
    device_registry = dr.async_get(hass)

    # -------------------------------------------------------------------------
    # Set up coordinators for each active electricity meter
    # -------------------------------------------------------------------------
    supports_live_consumption = config.get(CONFIG_MAIN_SUPPORTS_LIVE_CONSUMPTION, False)
    live_refresh_rate = config.get(
        CONFIG_MAIN_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
        CONFIG_DEFAULT_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
    )

    for point in account_info.get("electricity_meter_points", []) or []:
        mpan = point["mpan"]
        electricity_tariff = get_active_tariff(now, point["agreements"])

        # Remove stale HA devices if there's no active tariff
        if electricity_tariff is None:
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, f"electricity_{mpan}")}
            )
            if device is not None:
                _LOGGER.debug(f"Removing electricity device {mpan} — no active tariff")
                device_registry.async_remove_device(device.id)
            continue

        for meter in point["meters"]:
            serial_number = meter["serial_number"]
            device_id = meter.get("device_id")

            # Rates coordinator (polls every 30 mins)
            await async_setup_electricity_rates_coordinator(
                hass, account_id, mpan, serial_number
            )

            # Standing charge coordinator (polls every 60 mins)
            await async_setup_electricity_standing_charges_coordinator(
                hass, account_id, mpan, serial_number
            )

            # Previous consumption coordinator (polls yesterday's data)
            await async_create_previous_consumption_and_rates_coordinator(
                hass, account_id, client, mpan, serial_number, is_electricity=True
            )

            # Live smart meter consumption (only if user has SMETS2 and opted in)
            if supports_live_consumption and device_id is not None:
                coordinator = await async_create_current_consumption_coordinator(
                    hass,
                    account_id,
                    client,
                    device_id,
                    live_refresh_rate,
                )
                hass.data[DOMAIN][account_id][
                    DATA_CURRENT_CONSUMPTION_KEY.format(device_id)
                ] = None
                await coordinator.async_config_entry_first_refresh()

    # -------------------------------------------------------------------------
    # Account info coordinator — polls account balance, tariff etc every 60 mins
    # -------------------------------------------------------------------------
    await async_setup_account_info_coordinator(hass, account_id)
