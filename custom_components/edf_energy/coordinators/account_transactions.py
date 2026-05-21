# Bobby5291 2026 — EDF Energy / Kraken API

import logging
from datetime import datetime, timedelta

from homeassistant.util.dt import now
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import (
    COORDINATOR_REFRESH_IN_SECONDS,
    DATA_ACCOUNT_TRANSACTIONS_KEY,
    DATA_ACCOUNT_TRANSACTIONS_COORDINATOR_KEY,
    DOMAIN,
    REFRESH_RATE_IN_MINUTES_ACCOUNT,
)
from ..api_client import ApiException, EDFEnergyApiClient
from . import BaseCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class AccountTransactionsCoordinatorResult(BaseCoordinatorResult):
    transactions: list | None

    def __init__(self, last_evaluated: datetime, request_attempts: int,
                 transactions,
                 last_retrieved: datetime | None = None,
                 last_error: Exception | None = None):
        super().__init__(last_evaluated, request_attempts, REFRESH_RATE_IN_MINUTES_ACCOUNT, last_retrieved, last_error)
        self.transactions = transactions


async def async_refresh_account_transactions_data(
    current: datetime,
    client: EDFEnergyApiClient,
    account_id: str,
    existing: AccountTransactionsCoordinatorResult | None,
) -> AccountTransactionsCoordinatorResult:

    if existing is not None and current < existing.next_refresh:
        return existing

    raised_exception = None
    try:
        data = await client.async_get_account_transactions(account_id)
        if data is not None:
            return AccountTransactionsCoordinatorResult(current, 1, data)
    except Exception as e:
        if not isinstance(e, ApiException):
            raise
        raised_exception = e
        _LOGGER.debug(f'Failed to retrieve account transactions for {account_id}')

    if existing is not None:
        return AccountTransactionsCoordinatorResult(
            existing.last_evaluated,
            existing.request_attempts + 1,
            existing.transactions,
            existing.last_retrieved,
            last_error=raised_exception,
        )

    return AccountTransactionsCoordinatorResult(
        current - timedelta(minutes=REFRESH_RATE_IN_MINUTES_ACCOUNT),
        2, None, last_error=raised_exception,
    )


async def async_setup_account_transactions_coordinator(
    hass, account_id: str, client: EDFEnergyApiClient
):
    key = DATA_ACCOUNT_TRANSACTIONS_KEY.format(account_id)
    hass.data[DOMAIN][account_id][key] = None

    async def async_update_data():
        current = now()
        existing = hass.data[DOMAIN][account_id].get(key)
        result = await async_refresh_account_transactions_data(current, client, account_id, existing)
        hass.data[DOMAIN][account_id][key] = result
        return result

    coordinator_key = DATA_ACCOUNT_TRANSACTIONS_COORDINATOR_KEY.format(account_id)
    coordinator = DataUpdateCoordinator(
        hass, _LOGGER, name=key,
        update_method=async_update_data,
        update_interval=timedelta(seconds=COORDINATOR_REFRESH_IN_SECONDS),
        always_update=True,
    )
    hass.data[DOMAIN][account_id][coordinator_key] = coordinator
    return coordinator
