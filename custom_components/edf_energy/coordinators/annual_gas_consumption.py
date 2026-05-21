# Bobby5291 2026 — EDF Energy / Kraken API

import logging
from datetime import datetime, timedelta

from homeassistant.util.dt import now
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import (
    COORDINATOR_REFRESH_IN_SECONDS,
    DATA_ANNUAL_GAS_CONSUMPTION_KEY,
    DATA_ANNUAL_GAS_CONSUMPTION_COORDINATOR_KEY,
    DOMAIN,
    REFRESH_RATE_IN_MINUTES_ACCOUNT,
)
from ..api_client import ApiException, EDFEnergyApiClient
from . import BaseCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class AnnualGasConsumptionCoordinatorResult(BaseCoordinatorResult):
    aq: float | None
    supplier_name: str | None
    supplier_effective_from: str | None
    aq_effective_from: str | None

    def __init__(self, last_evaluated: datetime, request_attempts: int,
                 aq, supplier_name, supplier_effective_from, aq_effective_from,
                 last_retrieved: datetime | None = None,
                 last_error: Exception | None = None):
        super().__init__(last_evaluated, request_attempts, REFRESH_RATE_IN_MINUTES_ACCOUNT, last_retrieved, last_error)
        self.aq = aq
        self.supplier_name = supplier_name
        self.supplier_effective_from = supplier_effective_from
        self.aq_effective_from = aq_effective_from


async def async_refresh_annual_gas_consumption_data(
    current: datetime,
    client: EDFEnergyApiClient,
    target_mprn: str,
    existing: AnnualGasConsumptionCoordinatorResult | None,
) -> AnnualGasConsumptionCoordinatorResult:

    if existing is not None and current < existing.next_refresh:
        return existing

    raised_exception = None
    try:
        data = await client.async_get_annual_gas_consumption(target_mprn)
        if data is not None:
            return AnnualGasConsumptionCoordinatorResult(
                current, 1,
                data.get("aq"),
                data.get("supplier_name"),
                data.get("supplier_effective_from"),
                data.get("aq_effective_from"),
            )
    except Exception as e:
        if not isinstance(e, ApiException):
            raise
        raised_exception = e
        _LOGGER.debug(f'Failed to retrieve annual gas consumption for {target_mprn}')

    if existing is not None:
        result = AnnualGasConsumptionCoordinatorResult(
            existing.last_evaluated,
            existing.request_attempts + 1,
            existing.aq,
            existing.supplier_name,
            existing.supplier_effective_from,
            existing.aq_effective_from,
            existing.last_retrieved,
            last_error=raised_exception,
        )
        if result.request_attempts == 2:
            _LOGGER.warning(f"Failed to retrieve annual gas consumption for {target_mprn} — using cached data.")
        return result

    _LOGGER.warning(f"Failed to retrieve annual gas consumption for {target_mprn}.")
    return AnnualGasConsumptionCoordinatorResult(
        current - timedelta(minutes=REFRESH_RATE_IN_MINUTES_ACCOUNT),
        2, None, None, None, None,
        last_error=raised_exception,
    )


async def async_setup_annual_gas_consumption_coordinator(
    hass, account_id: str, client: EDFEnergyApiClient, target_mprn: str
):
    key = DATA_ANNUAL_GAS_CONSUMPTION_KEY.format(target_mprn)
    hass.data[DOMAIN][account_id][key] = None

    async def async_update_data():
        current = now()
        existing = hass.data[DOMAIN][account_id].get(key)
        result = await async_refresh_annual_gas_consumption_data(current, client, target_mprn, existing)
        hass.data[DOMAIN][account_id][key] = result
        return result

    coordinator_key = DATA_ANNUAL_GAS_CONSUMPTION_COORDINATOR_KEY.format(target_mprn)
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
