# Bobby5291 2026 — EDF Energy / Kraken API — Intelligent / EV coordinator

import logging
from datetime import datetime, timedelta

from homeassistant.util.dt import now
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import (
    COORDINATOR_REFRESH_IN_SECONDS,
    DOMAIN,
    DATA_CLIENT,
    DATA_INTELLIGENT_DEVICE_KEY,
    DATA_INTELLIGENT_COORDINATOR_KEY,
)
from ..api_client import ApiException, EDFEnergyApiClient
from . import BaseCoordinatorResult

_LOGGER = logging.getLogger(__name__)

REFRESH_RATE_IN_MINUTES_INTELLIGENT = 30


class IntelligentCoordinatorResult(BaseCoordinatorResult):
    def __init__(
        self,
        last_evaluated: datetime,
        request_attempts: int,
        current_state: str | None,
        is_suspended: bool,
        target_percentage: int | None,
        target_time: str | None,
        mode: str | None,
        planned_dispatches: list,
        completed_dispatches: list,
        last_retrieved: datetime | None = None,
        last_error: Exception | None = None,
    ):
        super().__init__(last_evaluated, request_attempts, REFRESH_RATE_IN_MINUTES_INTELLIGENT, last_retrieved, last_error)
        self.current_state = current_state
        self.is_suspended = is_suspended
        self.is_bump_charging = current_state == "BOOSTING"
        self.target_percentage = target_percentage
        self.target_time = target_time
        self.mode = mode
        self.planned_dispatches = planned_dispatches or []
        self.completed_dispatches = completed_dispatches or []


async def async_setup_intelligent_coordinator(hass, account_id: str, client: EDFEnergyApiClient, device_id: str):
    """Create and register the intelligent coordinator for an EV device."""

    async def async_update_data():
        current = now()
        existing: IntelligentCoordinatorResult | None = hass.data[DOMAIN][account_id].get(
            DATA_INTELLIGENT_COORDINATOR_KEY.format(device_id)
        )

        if existing is not None and current < existing.next_refresh:
            return existing

        try:
            device_info = await client.async_get_intelligent_device(account_id)
            dispatches = await client.async_get_intelligent_dispatches(account_id, device_id) or {}

            current_state = None
            is_suspended = False
            target_percentage = None
            target_time = None
            mode = None

            if device_info is not None:
                current_state = device_info.get("current_state")
                is_suspended = device_info.get("is_suspended", False)
                target_percentage = device_info.get("target_percentage")
                target_time = device_info.get("target_time")
                mode = device_info.get("mode")

            result = IntelligentCoordinatorResult(
                last_evaluated=current,
                request_attempts=1,
                current_state=current_state,
                is_suspended=is_suspended,
                target_percentage=target_percentage,
                target_time=target_time,
                mode=mode,
                planned_dispatches=dispatches.get("planned", []),
                completed_dispatches=dispatches.get("completed", []),
                last_retrieved=current,
            )
            hass.data[DOMAIN][account_id][DATA_INTELLIGENT_COORDINATOR_KEY.format(device_id)] = result
            return result

        except Exception as e:
            if not isinstance(e, ApiException):
                raise

            _LOGGER.warning(f"Failed to fetch intelligent data for device {device_id}: {e}")

            if existing is not None:
                return IntelligentCoordinatorResult(
                    last_evaluated=existing.last_evaluated,
                    request_attempts=existing.request_attempts + 1,
                    current_state=existing.current_state,
                    is_suspended=existing.is_suspended,
                    target_percentage=existing.target_percentage,
                    target_time=existing.target_time,
                    mode=existing.mode,
                    planned_dispatches=existing.planned_dispatches,
                    completed_dispatches=existing.completed_dispatches,
                    last_retrieved=existing.last_retrieved,
                    last_error=e,
                )

            return IntelligentCoordinatorResult(
                last_evaluated=current,
                request_attempts=1,
                current_state=None,
                is_suspended=False,
                target_percentage=None,
                target_time=None,
                mode=None,
                planned_dispatches=[],
                completed_dispatches=[],
                last_error=e,
            )

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"edf_energy_intelligent_{account_id}_{device_id}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=COORDINATOR_REFRESH_IN_SECONDS),
        always_update=True,
    )
    hass.data[DOMAIN][account_id][DATA_INTELLIGENT_COORDINATOR_KEY.format(device_id)] = None
    return coordinator
