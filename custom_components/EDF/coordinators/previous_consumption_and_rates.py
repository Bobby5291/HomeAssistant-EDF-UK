# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 — adapted for EDF Energy / Kraken API

from datetime import datetime, timedelta
import logging

from homeassistant.util.dt import utcnow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import (
    COORDINATOR_REFRESH_IN_SECONDS,
    DATA_ACCOUNT,
    DATA_PREVIOUS_CONSUMPTION_COORDINATOR_KEY,
    DOMAIN,
    EVENT_ELECTRICITY_PREVIOUS_CONSUMPTION_RATES,
    EVENT_GAS_PREVIOUS_CONSUMPTION_RATES,
    MINIMUM_CONSUMPTION_DATA_LENGTH,
    REFRESH_RATE_IN_MINUTES_PREVIOUS_CONSUMPTION,
)

from ..api_client import ApiException, EDFEnergyApiClient
from ..utils import private_rates_to_public_rates
from ..utils.rate_information import get_min_max_average_rates
from . import BaseCoordinatorResult, get_electricity_meter_tariff, get_gas_meter_tariff

_LOGGER = logging.getLogger(__name__)


def __get_interval_end(item):
    return (item["end"].timestamp(), item["end"].fold)


def __sort_consumption(consumption_data):
    sorted_data = consumption_data.copy()
    sorted_data.sort(key=__get_interval_end)
    return sorted_data


class PreviousConsumptionCoordinatorResult(BaseCoordinatorResult):
    consumption: list
    rates: list
    standing_charge: float

    def __init__(self, last_evaluated: datetime, request_attempts: int, consumption: list, rates: list, standing_charge, last_error: Exception | None = None):
        super().__init__(last_evaluated, request_attempts, REFRESH_RATE_IN_MINUTES_PREVIOUS_CONSUMPTION, None, last_error)
        self.consumption = consumption
        self.rates = rates
        self.standing_charge = standing_charge


async def async_fetch_consumption_and_rates(
    previous_data: PreviousConsumptionCoordinatorResult | None,
    current: datetime,
    account_info,
    client: EDFEnergyApiClient,
    identifier: str,
    serial_number: str,
    is_electricity: bool,
    fire_event,
) -> PreviousConsumptionCoordinatorResult | None:

    if previous_data is not None and current < previous_data.next_refresh:
        return previous_data

    if account_info is None:
        return previous_data

    tariff = (
        get_electricity_meter_tariff(current, account_info, identifier, serial_number)
        if is_electricity
        else get_gas_meter_tariff(current, account_info, identifier, serial_number)
    )

    if tariff is None:
        return previous_data

    period_from = utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    period_to = period_from + timedelta(days=1)

    try:
        if is_electricity:
            consumption_data = await client.async_get_electricity_consumption(identifier, serial_number, period_from, period_to)
            rate_data = await client.async_get_electricity_rates(tariff.product, tariff.code, period_from, period_to)
            standing_charge = await client.async_get_electricity_standing_charge(tariff.product, tariff.code, period_from, period_to)
        else:
            consumption_data = await client.async_get_gas_consumption(identifier, serial_number, period_from, period_to)
            rate_data = await client.async_get_gas_rates(tariff.product, tariff.code, period_from, period_to)
            standing_charge = await client.async_get_gas_standing_charge(tariff.product, tariff.code, period_from, period_to)

        _LOGGER.debug(f"{'electricity' if is_electricity else 'gas'} {identifier}/{serial_number}: consumption: {len(consumption_data) if consumption_data is not None else None}; rates: {len(rate_data) if rate_data is not None else None}")

        if (consumption_data is not None and
                len(consumption_data) >= MINIMUM_CONSUMPTION_DATA_LENGTH and
                rate_data is not None and
                len(rate_data) > 0 and
                standing_charge is not None):

            consumption_data = __sort_consumption(consumption_data)
            public_rates = private_rates_to_public_rates(rate_data)
            min_max_average = get_min_max_average_rates(public_rates)

            if is_electricity:
                fire_event(EVENT_ELECTRICITY_PREVIOUS_CONSUMPTION_RATES, {
                    "mpan": identifier,
                    "serial_number": serial_number,
                    "tariff_code": tariff.code,
                    "rates": public_rates,
                    "min_rate": min_max_average["min"],
                    "max_rate": min_max_average["max"],
                    "average_rate": min_max_average["average"],
                })
            else:
                fire_event(EVENT_GAS_PREVIOUS_CONSUMPTION_RATES, {
                    "mprn": identifier,
                    "serial_number": serial_number,
                    "tariff_code": tariff.code,
                    "rates": public_rates,
                    "min_rate": min_max_average["min"],
                    "max_rate": min_max_average["max"],
                    "average_rate": min_max_average["average"],
                })

            return PreviousConsumptionCoordinatorResult(
                current, 1, consumption_data, rate_data, standing_charge["value_inc_vat"]
            )

        return PreviousConsumptionCoordinatorResult(
            current,
            1,
            previous_data.consumption if previous_data is not None else None,
            previous_data.rates if previous_data is not None else None,
            previous_data.standing_charge if previous_data is not None else None,
        )

    except Exception as e:
        if not isinstance(e, ApiException):
            raise

        if previous_data is not None:
            result = PreviousConsumptionCoordinatorResult(
                previous_data.last_evaluated,
                previous_data.request_attempts + 1,
                previous_data.consumption,
                previous_data.rates,
                previous_data.standing_charge,
                last_error=e,
            )
            if result.request_attempts == 2:
                _LOGGER.warning(f"Failed to retrieve previous consumption for {'electricity' if is_electricity else 'gas'} {identifier}/{serial_number} - using cached data.")
        else:
            result = PreviousConsumptionCoordinatorResult(
                current - timedelta(minutes=REFRESH_RATE_IN_MINUTES_PREVIOUS_CONSUMPTION),
                2, None, None, None, last_error=e,
            )
            _LOGGER.warning(f"Failed to retrieve previous consumption for {'electricity' if is_electricity else 'gas'} {identifier}/{serial_number}.")

        return result


async def async_create_previous_consumption_and_rates_coordinator(
    hass,
    account_id: str,
    client: EDFEnergyApiClient,
    identifier: str,
    serial_number: str,
    is_electricity: bool,
):
    """Create previous consumption coordinator."""
    key = f'{identifier}_{serial_number}_previous_consumption_and_rates'

    async def async_update_data():
        account_result = hass.data[DOMAIN][account_id].get(DATA_ACCOUNT)
        account_info = account_result.account if account_result is not None else None
        previous_data = hass.data[DOMAIN][account_id].get(key)
        current = utcnow()

        result = await async_fetch_consumption_and_rates(
            previous_data,
            current,
            account_info,
            client,
            identifier,
            serial_number,
            is_electricity,
            hass.bus.async_fire,
        )

        if result is not None:
            hass.data[DOMAIN][account_id][key] = result

        return hass.data[DOMAIN][account_id].get(key)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=key,
        update_method=async_update_data,
        update_interval=timedelta(seconds=COORDINATOR_REFRESH_IN_SECONDS),
        always_update=True,
    )

    hass.data[DOMAIN][account_id][DATA_PREVIOUS_CONSUMPTION_COORDINATOR_KEY.format(identifier, serial_number)] = coordinator
    return coordinator
