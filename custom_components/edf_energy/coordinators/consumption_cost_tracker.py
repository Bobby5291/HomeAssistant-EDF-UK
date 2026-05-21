# Bobby5291 2026 — EDF Energy / Kraken API

import logging
from datetime import datetime, timedelta

from homeassistant.util.dt import now as ha_now, as_utc
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import (
    COORDINATOR_REFRESH_IN_SECONDS,
    DATA_ACCOUNT,
    DATA_CLIENT,
    DATA_ELECTRICITY_COST_TRACKER_KEY,
    DATA_ELECTRICITY_COST_TRACKER_COORDINATOR_KEY,
    DATA_GAS_COST_TRACKER_KEY,
    DATA_GAS_COST_TRACKER_COORDINATOR_KEY,
    DOMAIN,
    REFRESH_RATE_IN_MINUTES_PREVIOUS_CONSUMPTION,
)
from ..api_client import ApiException, EDFEnergyApiClient
from ..utils.conversions import consumption_cost_in_pence, pence_to_pounds_pence
from . import BaseCoordinatorResult, get_electricity_meter_tariff, get_gas_meter_tariff

_LOGGER = logging.getLogger(__name__)


class ConsumptionCostTrackerCoordinatorResult(BaseCoordinatorResult):
    daily_consumption: float | None
    daily_cost: float | None
    daily_reset: datetime | None
    weekly_consumption: float | None
    weekly_cost: float | None
    weekly_reset: datetime | None
    monthly_consumption: float | None
    monthly_cost: float | None
    monthly_reset: datetime | None

    def __init__(
        self,
        last_evaluated: datetime,
        request_attempts: int,
        daily_consumption,
        daily_cost,
        daily_reset,
        weekly_consumption,
        weekly_cost,
        weekly_reset,
        monthly_consumption,
        monthly_cost,
        monthly_reset,
        last_retrieved=None,
        last_error=None,
    ):
        super().__init__(last_evaluated, request_attempts, REFRESH_RATE_IN_MINUTES_PREVIOUS_CONSUMPTION, last_retrieved, last_error)
        self.daily_consumption = daily_consumption
        self.daily_cost = daily_cost
        self.daily_reset = daily_reset
        self.weekly_consumption = weekly_consumption
        self.weekly_cost = weekly_cost
        self.weekly_reset = weekly_reset
        self.monthly_consumption = monthly_consumption
        self.monthly_cost = monthly_cost
        self.monthly_reset = monthly_reset


def _calculate_period_cost(consumption_data, rate_data, standing_charge_pence_per_day, period_start, period_end):
    """
    Calculate consumption (kWh) and cost (GBP) for items within [period_start, period_end).
    standing_charge_pence_per_day is multiplied by the number of days that have started in the period.
    Returns (consumption, cost) or (None, None) if no data.
    """
    if not consumption_data or not rate_data:
        return None, None

    total_kwh = 0.0
    total_pence = 0.0
    matched = False

    for item in consumption_data:
        item_start = item["start"]
        if item_start < period_start or item_start >= period_end:
            continue

        matched = True
        kwh = item["consumption"]
        total_kwh += kwh

        for rate in rate_data:
            if rate["start"] <= item_start < rate["end"]:
                total_pence += consumption_cost_in_pence(kwh, rate["value_inc_vat"])
                break

    if not matched:
        return None, None

    days_started = max(1, int((period_end - period_start).total_seconds() / 86400) + 1)
    standing_pence = (standing_charge_pence_per_day or 0) * days_started
    total_cost = round(pence_to_pounds_pence(total_pence + standing_pence), 2)

    return round(total_kwh, 5), total_cost


async def async_setup_electricity_cost_tracker_coordinator(
    hass, account_id: str, client: EDFEnergyApiClient, mpan: str, serial_number: str
):
    """Coordinator that fetches electricity consumption for this month and slices into daily/weekly/monthly costs."""
    key = DATA_ELECTRICITY_COST_TRACKER_KEY.format(mpan, serial_number)

    async def async_update_data():
        current_local = ha_now()
        current_utc = as_utc(current_local)

        previous = hass.data[DOMAIN][account_id].get(key)
        if previous is not None and current_utc < previous.next_refresh:
            return previous

        account_result = hass.data[DOMAIN][account_id].get(DATA_ACCOUNT)
        account_info = account_result.account if account_result is not None else None
        if account_info is None:
            return previous

        tariff = get_electricity_meter_tariff(current_utc, account_info, mpan, serial_number)
        if tariff is None:
            return previous

        today_start = as_utc(current_local.replace(hour=0, minute=0, second=0, microsecond=0))
        week_start = as_utc(
            (current_local - timedelta(days=current_local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        )
        month_start = as_utc(current_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
        fetch_from = min(today_start, week_start, month_start)

        try:
            api_client: EDFEnergyApiClient = hass.data[DOMAIN][account_id][DATA_CLIENT]

            consumption_data = await api_client.async_get_electricity_consumption(
                mpan, serial_number, fetch_from, current_utc, page_size=1500
            )
            rate_data = await api_client.async_get_electricity_rates(
                tariff.product, tariff.code, fetch_from, current_utc
            )
            standing_charge_result = await api_client.async_get_electricity_standing_charge(
                tariff.product, tariff.code, fetch_from, current_utc
            )

            standing_charge_pence = standing_charge_result["value_inc_vat"] if standing_charge_result else None

            daily_c, daily_cost = _calculate_period_cost(consumption_data, rate_data, standing_charge_pence, today_start, current_utc)
            weekly_c, weekly_cost = _calculate_period_cost(consumption_data, rate_data, standing_charge_pence, week_start, current_utc)
            monthly_c, monthly_cost = _calculate_period_cost(consumption_data, rate_data, standing_charge_pence, month_start, current_utc)

            result = ConsumptionCostTrackerCoordinatorResult(
                current_utc, 1,
                daily_c, daily_cost, today_start,
                weekly_c, weekly_cost, week_start,
                monthly_c, monthly_cost, month_start,
            )
            hass.data[DOMAIN][account_id][key] = result
            return result

        except Exception as e:
            if not isinstance(e, ApiException):
                raise

            _LOGGER.debug(f"Cost tracker failed for {mpan}/{serial_number}: {e}")

            if previous is not None:
                result = ConsumptionCostTrackerCoordinatorResult(
                    previous.last_evaluated,
                    previous.request_attempts + 1,
                    previous.daily_consumption, previous.daily_cost, previous.daily_reset,
                    previous.weekly_consumption, previous.weekly_cost, previous.weekly_reset,
                    previous.monthly_consumption, previous.monthly_cost, previous.monthly_reset,
                    last_error=e,
                )
                if result.request_attempts == 2:
                    _LOGGER.warning(f"Failed to retrieve electricity cost tracker for {mpan}/{serial_number} - using cached.")
                hass.data[DOMAIN][account_id][key] = result
                return result

            return None

    coordinator_key = DATA_ELECTRICITY_COST_TRACKER_COORDINATOR_KEY.format(mpan, serial_number)
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=key,
        update_method=async_update_data,
        update_interval=timedelta(seconds=COORDINATOR_REFRESH_IN_SECONDS),
        always_update=True,
    )
    hass.data[DOMAIN][account_id][coordinator_key] = coordinator
    return coordinator


async def async_setup_gas_cost_tracker_coordinator(
    hass, account_id: str, client: EDFEnergyApiClient, mprn: str, serial_number: str
):
    """Coordinator that fetches gas consumption for this month and slices into daily/weekly/monthly costs."""
    key = DATA_GAS_COST_TRACKER_KEY.format(mprn, serial_number)

    async def async_update_data():
        current_local = ha_now()
        current_utc = as_utc(current_local)

        previous = hass.data[DOMAIN][account_id].get(key)
        if previous is not None and current_utc < previous.next_refresh:
            return previous

        account_result = hass.data[DOMAIN][account_id].get(DATA_ACCOUNT)
        account_info = account_result.account if account_result is not None else None
        if account_info is None:
            return previous

        tariff = get_gas_meter_tariff(current_utc, account_info, mprn, serial_number)
        if tariff is None:
            return previous

        today_start = as_utc(current_local.replace(hour=0, minute=0, second=0, microsecond=0))
        week_start = as_utc(
            (current_local - timedelta(days=current_local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        )
        month_start = as_utc(current_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
        fetch_from = min(today_start, week_start, month_start)

        try:
            api_client: EDFEnergyApiClient = hass.data[DOMAIN][account_id][DATA_CLIENT]

            consumption_data = await api_client.async_get_gas_consumption(
                mprn, serial_number, fetch_from, current_utc, page_size=1500
            )
            rate_data = await api_client.async_get_gas_rates(tariff.product, tariff.code, fetch_from, current_utc)
            standing_charge_result = await api_client.async_get_gas_standing_charge(
                tariff.product, tariff.code, fetch_from, current_utc
            )

            standing_charge_pence = standing_charge_result["value_inc_vat"] if standing_charge_result else None

            daily_c, daily_cost = _calculate_period_cost(consumption_data, rate_data, standing_charge_pence, today_start, current_utc)
            weekly_c, weekly_cost = _calculate_period_cost(consumption_data, rate_data, standing_charge_pence, week_start, current_utc)
            monthly_c, monthly_cost = _calculate_period_cost(consumption_data, rate_data, standing_charge_pence, month_start, current_utc)

            result = ConsumptionCostTrackerCoordinatorResult(
                current_utc, 1,
                daily_c, daily_cost, today_start,
                weekly_c, weekly_cost, week_start,
                monthly_c, monthly_cost, month_start,
            )
            hass.data[DOMAIN][account_id][key] = result
            return result

        except Exception as e:
            if not isinstance(e, ApiException):
                raise

            _LOGGER.debug(f"Gas cost tracker failed for {mprn}/{serial_number}: {e}")

            if previous is not None:
                result = ConsumptionCostTrackerCoordinatorResult(
                    previous.last_evaluated,
                    previous.request_attempts + 1,
                    previous.daily_consumption, previous.daily_cost, previous.daily_reset,
                    previous.weekly_consumption, previous.weekly_cost, previous.weekly_reset,
                    previous.monthly_consumption, previous.monthly_cost, previous.monthly_reset,
                    last_error=e,
                )
                if result.request_attempts == 2:
                    _LOGGER.warning(f"Failed to retrieve gas cost tracker for {mprn}/{serial_number} - using cached.")
                hass.data[DOMAIN][account_id][key] = result
                return result

            return None

    coordinator_key = DATA_GAS_COST_TRACKER_COORDINATOR_KEY.format(mprn, serial_number)
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=key,
        update_method=async_update_data,
        update_interval=timedelta(seconds=COORDINATOR_REFRESH_IN_SECONDS),
        always_update=True,
    )
    hass.data[DOMAIN][account_id][coordinator_key] = coordinator
    return coordinator
