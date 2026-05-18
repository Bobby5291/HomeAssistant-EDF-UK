# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 [year] — adapted for EDF Energy / Kraken API

import logging
from datetime import datetime, timedelta

from homeassistant.util.dt import now, as_utc
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import (
    COORDINATOR_REFRESH_IN_SECONDS,
    DATA_ACCOUNT,
    DATA_CLIENT,
    DATA_ELECTRICITY_STANDING_CHARGE_KEY,
    DATA_ELECTRICITY_STANDING_CHARGE_COORDINATOR_KEY,
    DOMAIN,
    REFRESH_RATE_IN_MINUTES_STANDING_CHARGE,
)

from ..api_client import ApiException, EDFEnergyApiClient
from . import BaseCoordinatorResult, get_electricity_meter_tariff

_LOGGER = logging.getLogger(__name__)


class ElectricityStandingChargeCoordinatorResult(BaseCoordinatorResult):
    standing_charge: dict

    def __init__(self, last_evaluated: datetime, request_attempts: int, standing_charge: dict, last_retrieved: datetime | None = None, last_error: Exception | None = None):
        super().__init__(last_evaluated, request_attempts, REFRESH_RATE_IN_MINUTES_STANDING_CHARGE, last_retrieved, last_error)
        self.standing_charge = standing_charge


async def async_refresh_electricity_standing_charges_data(
    current: datetime,
    client: EDFEnergyApiClient,
    account_info,
    target_mpan: str,
    target_serial_number: str,
    existing_result: ElectricityStandingChargeCoordinatorResult | None,
):
    period_from = as_utc(current.replace(hour=0, minute=0, second=0, microsecond=0))
    period_to = period_from + timedelta(days=1)

    if account_info is None:
        return existing_result

    tariff = get_electricity_meter_tariff(current, account_info, target_mpan, target_serial_number)
    if tariff is None:
        return None

    if existing_result is None or current >= existing_result.next_refresh:
        new_standing_charge = None
        raised_exception = None
        last_retrieved = None

        if (existing_result is not None and
                existing_result.standing_charge is not None and
                existing_result.standing_charge["tariff_code"] == tariff.code and
                (existing_result.standing_charge["start"] is None or existing_result.standing_charge["start"] <= period_from) and
                (existing_result.standing_charge["end"] is None or existing_result.standing_charge["end"] >= period_to)):
            _LOGGER.info('Cached electricity standing charge still valid, reusing')
            new_standing_charge = existing_result.standing_charge
            last_retrieved = existing_result.last_retrieved
        else:
            try:
                new_standing_charge = await client.async_get_electricity_standing_charge(tariff.product, tariff.code, period_from, period_to)
                _LOGGER.debug(f'Electricity standing charge retrieved for {target_mpan}/{target_serial_number} ({tariff.code})')
            except Exception as e:
                if not isinstance(e, ApiException):
                    raise
                raised_exception = e
                _LOGGER.debug(f'Failed to retrieve electricity standing charge for {target_mpan}/{target_serial_number} ({tariff.code})')

        if new_standing_charge is not None:
            return ElectricityStandingChargeCoordinatorResult(current, 1, new_standing_charge, last_retrieved)

        if existing_result is not None:
            result = ElectricityStandingChargeCoordinatorResult(
                existing_result.last_evaluated,
                existing_result.request_attempts + 1,
                existing_result.standing_charge,
                existing_result.last_retrieved,
                last_error=raised_exception,
            )
            if result.request_attempts == 2:
                _LOGGER.warning(f"Failed to retrieve electricity standing charge for {target_mpan}/{target_serial_number} - using cached.")
        else:
            result = ElectricityStandingChargeCoordinatorResult(
                current - timedelta(minutes=REFRESH_RATE_IN_MINUTES_STANDING_CHARGE),
                2,
                None,
                last_error=raised_exception,
            )
            _LOGGER.warning(f"Failed to retrieve electricity standing charge for {target_mpan}/{target_serial_number}.")

        return result

    return existing_result


async def async_setup_electricity_standing_charges_coordinator(hass, account_id: str, target_mpan: str, target_serial_number: str):
    key = DATA_ELECTRICITY_STANDING_CHARGE_KEY.format(target_mpan, target_serial_number)
    hass.data[DOMAIN][account_id][key] = None

    async def async_update_data():
        current = now()
        client: EDFEnergyApiClient = hass.data[DOMAIN][account_id][DATA_CLIENT]
        account_result = hass.data[DOMAIN][account_id].get(DATA_ACCOUNT)
        account_info = account_result.account if account_result is not None else None
        existing = hass.data[DOMAIN][account_id].get(key)

        hass.data[DOMAIN][account_id][key] = await async_refresh_electricity_standing_charges_data(
            current, client, account_info, target_mpan, target_serial_number, existing
        )

        return hass.data[DOMAIN][account_id][key]

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=key,
        update_method=async_update_data,
        update_interval=timedelta(seconds=COORDINATOR_REFRESH_IN_SECONDS),
        always_update=True,
    )

    coordinator_key = DATA_ELECTRICITY_STANDING_CHARGE_COORDINATOR_KEY.format(target_mpan, target_serial_number)
    hass.data[DOMAIN][account_id][coordinator_key] = coordinator
    return coordinator
