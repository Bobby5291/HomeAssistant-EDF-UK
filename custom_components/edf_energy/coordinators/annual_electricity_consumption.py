# Bobby5291 2026 — EDF Energy / Kraken API

import logging
from datetime import datetime, timedelta

from homeassistant.util.dt import now
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import (
    COORDINATOR_REFRESH_IN_SECONDS,
    DATA_ANNUAL_ELECTRICITY_CONSUMPTION_KEY,
    DATA_ANNUAL_ELECTRICITY_CONSUMPTION_COORDINATOR_KEY,
    DOMAIN,
    REFRESH_RATE_IN_MINUTES_ACCOUNT,
)
from ..api_client import ApiException, AuthenticationException, EDFEnergyApiClient
from . import BaseCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class AnnualElectricityConsumptionCoordinatorResult(BaseCoordinatorResult):
    eac_standard: float | None
    eac_day: float | None
    eac_night: float | None

    def __init__(self, last_evaluated: datetime, request_attempts: int,
                 eac_standard, eac_day, eac_night,
                 last_retrieved: datetime | None = None,
                 last_error: Exception | None = None):
        super().__init__(last_evaluated, request_attempts, REFRESH_RATE_IN_MINUTES_ACCOUNT, last_retrieved, last_error)
        self.eac_standard = eac_standard
        self.eac_day = eac_day
        self.eac_night = eac_night


async def async_refresh_annual_electricity_consumption_data(
    current: datetime,
    client: EDFEnergyApiClient,
    target_mpan: str,
    existing: AnnualElectricityConsumptionCoordinatorResult | None,
) -> AnnualElectricityConsumptionCoordinatorResult:

    if existing is not None and current < existing.next_refresh:
        return existing

    raised_exception = None
    is_not_yet_eligible = False
    try:
        data = await client.async_get_extended_electricity_consumption(target_mpan)
        if data is not None:
            return AnnualElectricityConsumptionCoordinatorResult(
                current, 1,
                data.get("eac_standard"),
                data.get("eac_day"),
                data.get("eac_night"),
            )
    except Exception as e:
        if not isinstance(e, ApiException):
            raise
        raised_exception = e
        is_not_yet_eligible = isinstance(e, AuthenticationException)
        if is_not_yet_eligible:
            _LOGGER.debug(
                f"Annual electricity consumption for {target_mpan} is not available "
                "(AUTHORIZATION/KT-CT-1111) — this normally means the account hasn't "
                "been with EDF long enough yet for an estimate to be calculated."
            )
        else:
            _LOGGER.debug(f'Failed to retrieve annual electricity consumption for {target_mpan}')

    if existing is not None:
        result = AnnualElectricityConsumptionCoordinatorResult(
            existing.last_evaluated,
            existing.request_attempts + 1,
            existing.eac_standard,
            existing.eac_day,
            existing.eac_night,
            existing.last_retrieved,
            last_error=raised_exception,
        )
        if result.request_attempts == 2 and not is_not_yet_eligible:
            _LOGGER.warning(f"Failed to retrieve annual electricity consumption for {target_mpan} — using cached data.")
        return result

    if not is_not_yet_eligible:
        _LOGGER.warning(f"Failed to retrieve annual electricity consumption for {target_mpan}.")
    return AnnualElectricityConsumptionCoordinatorResult(
        current - timedelta(minutes=REFRESH_RATE_IN_MINUTES_ACCOUNT),
        2, None, None, None,
        last_error=raised_exception,
    )


async def async_setup_annual_electricity_consumption_coordinator(
    hass, account_id: str, client: EDFEnergyApiClient, target_mpan: str
):
    key = DATA_ANNUAL_ELECTRICITY_CONSUMPTION_KEY.format(target_mpan)
    hass.data[DOMAIN][account_id][key] = None

    async def async_update_data():
        current = now()
        existing = hass.data[DOMAIN][account_id].get(key)
        result = await async_refresh_annual_electricity_consumption_data(current, client, target_mpan, existing)
        hass.data[DOMAIN][account_id][key] = result
        return result

    coordinator_key = DATA_ANNUAL_ELECTRICITY_CONSUMPTION_COORDINATOR_KEY.format(target_mpan)
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
