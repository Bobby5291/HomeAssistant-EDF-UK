# Bobby5291 2026 — EDF Energy / Kraken API — HA Diagnostics endpoint

import copy
import logging
from datetime import timedelta

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import now

from .const import CONFIG_ACCOUNT_ID, DATA_ACCOUNT, DATA_CLIENT, DOMAIN
from .api_client import EDFEnergyApiClient, TimeoutException
from .utils.attributes import dict_to_typed_dict

_LOGGER = logging.getLogger(__name__)

_REDACT_CONFIG = {CONFIG_ACCOUNT_ID, "email", "password", "refresh_token"}
_SKIP_ATTRIBUTES = {"mpan", "mprn", "serial_number", "friendly_name", "icon", "unit_of_measurement", "device_class", "state_class", "account_id"}


async def _get_recent_device_consumption(client: EDFEnergyApiClient, device_id: str):
    current = now()
    try:
        data = await client.async_get_smart_meter_consumption(device_id, current - timedelta(minutes=120), current)
        if data and len(data) > 0:
            return data[-1]
        return "No data available"
    except Exception as e:
        return f"Failed: {e}"


async def async_get_config_entry_diagnostics(hass, entry):
    """Return diagnostics for the config entry (lightweight — timestamps only)."""
    config = dict(entry.data)
    account_id = config[CONFIG_ACCOUNT_ID]
    account_result = hass.data[DOMAIN][account_id].get(DATA_ACCOUNT)
    account_info_raw = account_result.account if account_result is not None else None
    client: EDFEnergyApiClient = hass.data[DOMAIN][account_id].get(DATA_CLIENT)

    redacted_mappings, account_info = _redact_account_info(account_info_raw)

    entity_registry = er.async_get(hass)
    entity_info = {}
    for _eid, entry_obj in entity_registry.entities.items():
        uid = entry_obj.unique_id
        if "edf_energy" not in uid:
            continue
        state = hass.states.get(entry_obj.entity_id)
        for key, val in redacted_mappings.items():
            uid = uid.lower().replace(key.lower(), str(val))
        entity_info[uid] = {
            "last_updated": state.last_updated if state else None,
            "last_changed": state.last_changed if state else None,
        }

    return {
        "timestamp_captured": now(),
        "account": account_info,
        "using_cached_account_data": account_info_raw is not None,
        "entities": entity_info,
        "config_entry": async_redact_data(config, _REDACT_CONFIG),
    }


async def async_get_device_diagnostics(hass, entry, device):
    """Return full diagnostics for a device (includes entity states)."""
    config = dict(entry.data)
    account_id = config[CONFIG_ACCOUNT_ID]
    account_result = hass.data[DOMAIN][account_id].get(DATA_ACCOUNT)
    account_info_raw = account_result.account if account_result is not None else None
    client: EDFEnergyApiClient = hass.data[DOMAIN][account_id].get(DATA_CLIENT)

    redacted_mappings, account_info = _redact_account_info(account_info_raw)

    # Enrich with latest consumption timestamps
    if account_info is not None and client is not None:
        for point in account_info.get("electricity_meter_points", []) or []:
            for meter in point.get("meters", []):
                try:
                    readings = await client.async_get_electricity_consumption(point["mpan"], meter["serial_number"], page_size=1)
                    meter["latest_consumption"] = readings[-1]["end"] if readings else "No data"
                except TimeoutException:
                    meter["latest_consumption"] = "Timeout"
                if meter.get("device_id"):
                    meter["latest_device_consumption"] = await _get_recent_device_consumption(client, meter["device_id"])

        for point in account_info.get("gas_meter_points", []) or []:
            for meter in point.get("meters", []):
                try:
                    readings = await client.async_get_gas_consumption(point["mprn"], meter["serial_number"], page_size=1)
                    meter["latest_consumption"] = readings[-1]["end"] if readings else "No data"
                except TimeoutException:
                    meter["latest_consumption"] = "Timeout"

    entity_registry = er.async_get(hass)
    entity_info = {}
    for _eid, entry_obj in entity_registry.entities.items():
        uid = entry_obj.unique_id
        if "edf_energy" not in uid:
            continue
        state = hass.states.get(entry_obj.entity_id)
        for key, val in redacted_mappings.items():
            uid = uid.lower().replace(key.lower(), str(val))
        entity_info[uid] = {
            "state": state.state if state else None,
            "attributes": dict_to_typed_dict(state.attributes, _SKIP_ATTRIBUTES) if state else None,
            "last_updated": state.last_updated if state else None,
            "last_changed": state.last_changed if state else None,
        }

    return {
        "timestamp_captured": now(),
        "account": account_info,
        "using_cached_account_data": account_info_raw is not None,
        "entities": entity_info,
        "config_entry": async_redact_data(config, _REDACT_CONFIG),
    }


def _redact_account_info(account_info_raw: dict | None):
    """Deep-copy account info and replace sensitive IDs with numeric tokens."""
    if account_info_raw is None:
        return {}, None

    account_info = copy.deepcopy(account_info_raw)
    mappings = {}
    counter = 1

    if account_info.get("id"):
        mappings[account_info["id"]] = "A"
        account_info["id"] = "A"

    for point in account_info.get("electricity_meter_points", []) or []:
        for meter in point.get("meters", []):
            sn = str(meter.get("serial_number", ""))
            if sn:
                mappings[sn] = counter
                meter["serial_number"] = counter
                counter += 1
            meter.pop("device_id", None)
        mpan = str(point.get("mpan", ""))
        if mpan:
            mappings[mpan] = counter
            point["mpan"] = counter
            counter += 1

    for point in account_info.get("gas_meter_points", []) or []:
        for meter in point.get("meters", []):
            sn = str(meter.get("serial_number", ""))
            if sn:
                mappings[sn] = counter
                meter["serial_number"] = counter
                counter += 1
            meter.pop("device_id", None)
        mprn = str(point.get("mprn", ""))
        if mprn:
            mappings[mprn] = counter
            point["mprn"] = counter
            counter += 1

    return mappings, account_info
