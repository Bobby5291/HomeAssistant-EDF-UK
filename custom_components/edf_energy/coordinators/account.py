# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging
from datetime import datetime, timedelta
from typing import Callable

from homeassistant.util.dt import now
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import issue_registry as ir

from ..const import (
    COORDINATOR_REFRESH_IN_SECONDS,
    DOMAIN,
    DATA_CLIENT,
    DATA_ACCOUNT,
    DATA_ACCOUNT_COORDINATOR,
    REFRESH_RATE_IN_MINUTES_ACCOUNT,
    REPAIR_ACCOUNT_NOT_FOUND,
    REPAIR_INVALID_CREDENTIALS,
)

from ..api_client import ApiException, AuthenticationException, EDFEnergyApiClient
from . import BaseCoordinatorResult
from ..utils import get_active_tariff

_LOGGER = logging.getLogger(__name__)


class AccountCoordinatorResult(BaseCoordinatorResult):
    account: dict

    def __init__(self, last_evaluated: datetime, request_attempts: int, account: dict, last_error: Exception | None = None):
        super().__init__(last_evaluated, request_attempts, REFRESH_RATE_IN_MINUTES_ACCOUNT, None, last_error)
        self.account = account


def raise_account_not_found(hass, account_id: str):
    ir.async_create_issue(
        hass,
        DOMAIN,
        REPAIR_ACCOUNT_NOT_FOUND.format(account_id),
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="account_not_found",
        translation_placeholders={"account_id": account_id},
    )


def raise_invalid_credentials(hass, account_id: str):
    ir.async_create_issue(
        hass,
        DOMAIN,
        REPAIR_INVALID_CREDENTIALS.format(account_id),
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="invalid_credentials",
        translation_placeholders={"account_id": account_id},
    )


def clear_issue(hass, key: str):
    ir.async_delete_issue(hass, DOMAIN, key)


def raise_meter_added(hass, account_id: str, mprn_mpan: str, serial_number: str, is_electricity: bool):
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"meter_added_{account_id}_{mprn_mpan}_{serial_number}_{is_electricity}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="meter_added",
        translation_placeholders={
            "account_id": account_id,
            "mprn_mpan": mprn_mpan,
            "serial_number": serial_number,
            "meter_type": "Electricity" if is_electricity else "Gas",
        },
    )


def raise_meter_removed(hass, account_id: str, mprn_mpan: str, serial_number: str, is_electricity: bool):
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"meter_removed_{account_id}_{mprn_mpan}_{serial_number}_{is_electricity}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="meter_removed",
        translation_placeholders={
            "account_id": account_id,
            "mprn_mpan": mprn_mpan,
            "serial_number": serial_number,
            "meter_type": "Electricity" if is_electricity else "Gas",
        },
    )


def get_active_electricity_meters(current: datetime, account_info: dict) -> dict[tuple[str, str], str]:
    unique_meters = {}
    if account_info is not None:
        for point in account_info.get("electricity_meter_points", []) or []:
            active_tariff = get_active_tariff(current, point["agreements"])
            if active_tariff is not None:
                for meter in point["meters"]:
                    key = (point["mpan"], meter["serial_number"])
                    unique_meters[key] = active_tariff
    return unique_meters


def get_active_gas_meters(current: datetime, account_info: dict) -> dict[tuple[str, str], str]:
    unique_meters = {}
    if account_info is not None:
        for point in account_info.get("gas_meter_points", []) or []:
            active_tariff = get_active_tariff(current, point["agreements"])
            if active_tariff is not None:
                for meter in point["meters"]:
                    key = (point["mprn"], meter["serial_number"])
                    unique_meters[key] = active_tariff
    return unique_meters


def check_for_removed_and_added_meters(
    account_id: str,
    previous_meters: dict[tuple[str, str], str],
    current_meters: dict[tuple[str, str], str],
    is_electricity: bool,
    raise_meter_removed: Callable[[str, str, bool], None],
    raise_meter_added: Callable[[str, str, bool], None],
    clear_issue: Callable[[str], None],
):
    for previous_key in previous_meters.keys():
        clear_issue(f"meter_removed_{account_id}_{previous_key[0]}_{previous_key[1]}_{is_electricity}")
        if previous_key not in current_meters:
            raise_meter_removed(previous_key[0], previous_key[1], is_electricity)

    for current_key in current_meters.keys():
        clear_issue(f"meter_added_{account_id}_{current_key[0]}_{current_key[1]}_{is_electricity}")
        if current_key not in previous_meters:
            raise_meter_added(current_key[0], current_key[1], is_electricity)


async def async_refresh_account(
    current: datetime,
    client: EDFEnergyApiClient,
    account_id: str,
    previous_request: AccountCoordinatorResult,
    raise_account_not_found: Callable[[], None],
    raise_invalid_credentials: Callable[[], None],
    raise_meter_removed: Callable[[str, str, bool], None],
    raise_meter_added: Callable[[str, str, bool], None],
    clear_issue: Callable[[str], None],
):
    if current >= previous_request.next_refresh:
        account_info = None
        try:
            account_info = await client.async_get_account(account_id)

            if account_info is None:
                raise_account_not_found()
            else:
                _LOGGER.debug("Account information retrieved")

                # Clear any existing repair issues
                clear_issue(REPAIR_ACCOUNT_NOT_FOUND.format(account_id))
                clear_issue(REPAIR_INVALID_CREDENTIALS.format(account_id))

                # Check for meter changes since last poll
                previous_electricity_meters = get_active_electricity_meters(current, previous_request.account) if previous_request.account is not None else {}
                previous_gas_meters = get_active_gas_meters(current, previous_request.account) if previous_request.account is not None else {}
                current_electricity_meters = get_active_electricity_meters(current, account_info)
                current_gas_meters = get_active_gas_meters(current, account_info)

                check_for_removed_and_added_meters(
                    account_id, previous_electricity_meters, current_electricity_meters, True,
                    raise_meter_removed, raise_meter_added, clear_issue
                )
                check_for_removed_and_added_meters(
                    account_id, previous_gas_meters, current_gas_meters, False,
                    raise_meter_removed, raise_meter_added, clear_issue
                )

                return AccountCoordinatorResult(current, 1, account_info)

        except Exception as e:
            if not isinstance(e, ApiException):
                raise

            if isinstance(e, AuthenticationException):
                raise_invalid_credentials()

            result = AccountCoordinatorResult(
                previous_request.last_evaluated,
                previous_request.request_attempts + 1,
                previous_request.account,
                last_error=e,
            )

            if result.request_attempts == 2:
                _LOGGER.warning("Failed to retrieve account information - using cached version.")

            return result

    return previous_request


async def async_setup_account_info_coordinator(hass, account_id: str):
    """Set up the account coordinator that polls EDF every 60 minutes."""

    async def async_update_account_data():
        """Fetch data from EDF API."""
        current = now()
        client: EDFEnergyApiClient = hass.data[DOMAIN][account_id][DATA_CLIENT]

        if DATA_ACCOUNT not in hass.data[DOMAIN][account_id] or hass.data[DOMAIN][account_id][DATA_ACCOUNT] is None:
            raise Exception("Failed to find account information")

        hass.data[DOMAIN][account_id][DATA_ACCOUNT] = await async_refresh_account(
            current,
            client,
            account_id,
            hass.data[DOMAIN][account_id][DATA_ACCOUNT],
            lambda: raise_account_not_found(hass, account_id),
            lambda: raise_invalid_credentials(hass, account_id),
            lambda mprn_mpan, serial_number, is_electricity: raise_meter_removed(hass, account_id, mprn_mpan, serial_number, is_electricity),
            lambda mprn_mpan, serial_number, is_electricity: raise_meter_added(hass, account_id, mprn_mpan, serial_number, is_electricity),
            lambda key: clear_issue(hass, key),
        )

        return hass.data[DOMAIN][account_id][DATA_ACCOUNT]

    hass.data[DOMAIN][account_id][DATA_ACCOUNT_COORDINATOR] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"edf_energy_account_{account_id}",
        update_method=async_update_account_data,
        # Runs every minute but only actually calls the API based on REFRESH_RATE_IN_MINUTES_ACCOUNT
        update_interval=timedelta(seconds=COORDINATOR_REFRESH_IN_SECONDS),
        always_update=True,
    )
