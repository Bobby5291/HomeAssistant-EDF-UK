# Bobby5291 2026 — EDF Energy / Kraken API

import logging
from datetime import datetime, timedelta

from homeassistant.util.dt import now
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import (
    COORDINATOR_REFRESH_IN_SECONDS,
    DATA_ELECTRICITY_METER_READINGS_KEY,
    DATA_ELECTRICITY_METER_READINGS_COORDINATOR_KEY,
    DOMAIN,
    REFRESH_RATE_IN_MINUTES_ACCOUNT,
)
from ..api_client import ApiException, EDFEnergyApiClient
from . import BaseCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class ElectricityMeterReadingsCoordinatorResult(BaseCoordinatorResult):
    read_at: str | None
    value: float | None

    def __init__(self, last_evaluated: datetime, request_attempts: int,
                 read_at, value,
                 last_retrieved: datetime | None = None,
                 last_error: Exception | None = None):
        super().__init__(last_evaluated, request_attempts, REFRESH_RATE_IN_MINUTES_ACCOUNT, last_retrieved, last_error)
        self.read_at = read_at
        self.value = value


async def async_refresh_electricity_meter_readings_data(
    current: datetime,
    client: EDFEnergyApiClient,
    target_mpan: str,
    target_serial_number: str,
    existing: ElectricityMeterReadingsCoordinatorResult | None,
) -> ElectricityMeterReadingsCoordinatorResult:

    if existing is not None and current < existing.next_refresh:
        return existing

    raised_exception = None
    try:
        data = await client.async_get_electricity_meter_readings(target_mpan, target_serial_number)
        if data is not None:
            return ElectricityMeterReadingsCoordinatorResult(
                current, 1, data.get("read_at"), data.get("value")
            )
    except Exception as e:
        if not isinstance(e, ApiException):
            raise
        raised_exception = e
        _LOGGER.debug(f'Failed to retrieve electricity meter readings for {target_mpan}/{target_serial_number}')

    if existing is not None:
        return ElectricityMeterReadingsCoordinatorResult(
            existing.last_evaluated,
            existing.request_attempts + 1,
            existing.read_at, existing.value,
            existing.last_retrieved,
            last_error=raised_exception,
        )

    return ElectricityMeterReadingsCoordinatorResult(
        current - timedelta(minutes=REFRESH_RATE_IN_MINUTES_ACCOUNT),
        2, None, None, last_error=raised_exception,
    )


async def async_setup_electricity_meter_readings_coordinator(
    hass, account_id: str, client: EDFEnergyApiClient,
    target_mpan: str, target_serial_number: str
):
    key = DATA_ELECTRICITY_METER_READINGS_KEY.format(target_mpan, target_serial_number)
    hass.data[DOMAIN][account_id][key] = None

    async def async_update_data():
        current = now()
        existing = hass.data[DOMAIN][account_id].get(key)
        result = await async_refresh_electricity_meter_readings_data(
            current, client, target_mpan, target_serial_number, existing
        )
        hass.data[DOMAIN][account_id][key] = result
        return result

    coordinator_key = DATA_ELECTRICITY_METER_READINGS_COORDINATOR_KEY.format(target_mpan, target_serial_number)
    coordinator = DataUpdateCoordinator(
        hass, _LOGGER, name=key,
        update_method=async_update_data,
        update_interval=timedelta(seconds=COORDINATOR_REFRESH_IN_SECONDS),
        always_update=True,
    )
    hass.data[DOMAIN][account_id][coordinator_key] = coordinator
    return coordinator
