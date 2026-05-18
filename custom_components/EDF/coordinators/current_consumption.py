# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 — adapted for EDF Energy / Kraken API

from datetime import datetime, timedelta
import logging

from homeassistant.util.dt import now
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import (
    COORDINATOR_REFRESH_IN_SECONDS,
    DATA_CURRENT_CONSUMPTION_KEY,
    DOMAIN,
)

from ..api_client import ApiException, EDFEnergyApiClient
from . import BaseCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class CurrentConsumptionCoordinatorResult(BaseCoordinatorResult):
    data: list

    def __init__(self, last_evaluated: datetime, request_attempts: int, refresh_rate_in_minutes: float, data: list, last_error: Exception | None = None):
        super().__init__(last_evaluated, request_attempts, refresh_rate_in_minutes, None, last_error)
        self.data = data


async def async_get_live_consumption(
    current_date: datetime,
    client: EDFEnergyApiClient,
    device_id: str,
    previous_consumption: CurrentConsumptionCoordinatorResult | None,
    refresh_rate_in_minutes: float,
):
    if previous_consumption is None or current_date >= previous_consumption.next_refresh:
        period_from = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
        period_to = period_from + timedelta(days=1)

        try:
            data = await client.async_get_smart_meter_consumption(device_id, period_from, period_to)
            if data is not None:
                _LOGGER.debug(f'Retrieved smart meter consumption for {device_id}; slots: {len(data)}')
                return CurrentConsumptionCoordinatorResult(current_date, 1, refresh_rate_in_minutes, data)
        except Exception as e:
            if not isinstance(e, ApiException):
                raise

            if previous_consumption is not None:
                result = CurrentConsumptionCoordinatorResult(
                    previous_consumption.last_evaluated,
                    previous_consumption.request_attempts + 1,
                    refresh_rate_in_minutes,
                    previous_consumption.data,
                    last_error=e,
                )
                if result.request_attempts == 2:
                    _LOGGER.warning(f'Failed to retrieve smart meter consumption for {device_id} - using cached version.')
            else:
                result = CurrentConsumptionCoordinatorResult(
                    current_date - timedelta(minutes=refresh_rate_in_minutes),
                    2,
                    refresh_rate_in_minutes,
                    None,
                    last_error=e,
                )
                _LOGGER.warning(f'Failed to retrieve smart meter consumption for {device_id}.')

            return result

    return previous_consumption


async def async_create_current_consumption_coordinator(hass, account_id: str, client: EDFEnergyApiClient, device_id: str, refresh_rate_in_minutes: float):
    """Create current consumption coordinator for a smart meter device."""
    key = DATA_CURRENT_CONSUMPTION_KEY.format(device_id)
    hass.data[DOMAIN][account_id][key] = None

    async def async_update_data():
        current: datetime = now()
        previous_consumption = hass.data[DOMAIN][account_id].get(key)
        hass.data[DOMAIN][account_id][key] = await async_get_live_consumption(
            current,
            client,
            device_id,
            previous_consumption,
            refresh_rate_in_minutes,
        )
        return hass.data[DOMAIN][account_id][key]

    return DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"edf_energy_consumption_{device_id}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=COORDINATOR_REFRESH_IN_SECONDS),
        always_update=True,
    )
