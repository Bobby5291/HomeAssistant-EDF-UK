# Bobby5291 2026 — EDF Energy / Kraken API — EV smart dispatch calendars

import logging
from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import now as ha_now

from .intelligent import EDFEnergyIntelligentDevice
from .coordinators.intelligent import IntelligentCoordinatorResult
from .const import (
    CONFIG_ACCOUNT_ID,
    DATA_INTELLIGENT_COORDINATOR_KEY,
    DATA_INTELLIGENT_DEVICE_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up EDF Energy intelligent calendar entities."""
    config = dict(entry.data)
    account_id = config[CONFIG_ACCOUNT_ID]

    device_info = hass.data[DOMAIN][account_id].get(DATA_INTELLIGENT_DEVICE_KEY.format(account_id))
    if device_info is None:
        return

    device_id = device_info["id"]
    coordinator_key = DATA_INTELLIGENT_COORDINATOR_KEY.format(device_id)
    coordinator = hass.data[DOMAIN][account_id].get(coordinator_key)
    if coordinator is None:
        return

    async_add_entities([
        EDFEnergyIntelligentPlannedDispatchesCalendar(hass, coordinator, account_id, device_info),
        EDFEnergyIntelligentCompletedDispatchesCalendar(hass, coordinator, account_id, device_info),
    ])


def _dispatch_to_event(dispatch: dict, summary: str) -> CalendarEvent:
    return CalendarEvent(
        start=dispatch["start"],
        end=dispatch["end"],
        summary=summary,
        description=str({k: v for k, v in dispatch.items() if k not in ("start", "end")}),
    )


class _IntelligentCalendarBase(CoordinatorEntity, EDFEnergyIntelligentDevice, CalendarEntity):

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str, device_info: dict):
        self._device_id = device_info["id"]
        EDFEnergyIntelligentDevice.__init__(
            self, hass, account_id, self._device_id,
            device_info.get("make"), device_info.get("model"), device_info.get("device_type")
        )
        CoordinatorEntity.__init__(self, coordinator)

    @callback
    def _handle_coordinator_update(self) -> None:
        super()._handle_coordinator_update()


class EDFEnergyIntelligentPlannedDispatchesCalendar(_IntelligentCalendarBase):
    """Calendar showing upcoming planned smart charge windows."""

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._device_id}_intelligent_planned_dispatches"

    @property
    def name(self):
        return f"EDF Intelligent Planned Dispatches ({self._account_id})"

    @property
    def icon(self):
        return "mdi:calendar-clock"

    @property
    def event(self) -> CalendarEvent | None:
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is None:
            return None
        current = ha_now()
        for d in sorted(result.planned_dispatches, key=lambda x: x["start"]):
            if d["end"] > current:
                return _dispatch_to_event(d, "EDF Smart Charge Window")
        return None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime):
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is None:
            return []
        return [
            _dispatch_to_event(d, "EDF Smart Charge Window")
            for d in result.planned_dispatches
            if d["start"] < end_date and d["end"] > start_date
        ]


class EDFEnergyIntelligentCompletedDispatchesCalendar(_IntelligentCalendarBase):
    """Calendar showing completed (historical) charge sessions."""

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._device_id}_intelligent_completed_dispatches"

    @property
    def name(self):
        return f"EDF Intelligent Completed Dispatches ({self._account_id})"

    @property
    def icon(self):
        return "mdi:calendar-check"

    @property
    def event(self) -> CalendarEvent | None:
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is None:
            return None
        if not result.completed_dispatches:
            return None
        most_recent = max(result.completed_dispatches, key=lambda x: x["start"])
        return _dispatch_to_event(most_recent, "EDF Completed Charge Session")

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime):
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is None:
            return []
        return [
            _dispatch_to_event(d, "EDF Completed Charge Session")
            for d in result.completed_dispatches
            if d["start"] < end_date and d["end"] > start_date
        ]
