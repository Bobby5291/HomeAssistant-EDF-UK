# Bobby5291 2026 — EDF Energy / Kraken API — Intelligent target time entity (TIME platform)

import logging
from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .intelligent import EDFEnergyIntelligentDevice
from .coordinators.intelligent import IntelligentCoordinatorResult
from .const import (
    CONFIG_ACCOUNT_ID,
    DATA_CLIENT,
    DATA_INTELLIGENT_COORDINATOR_KEY,
    DATA_INTELLIGENT_DEVICE_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TARGET_PCT = 80


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up EDF Energy intelligent time entities."""
    config = dict(entry.data)
    account_id = config[CONFIG_ACCOUNT_ID]

    device_info = hass.data[DOMAIN][account_id].get(DATA_INTELLIGENT_DEVICE_KEY.format(account_id))
    if device_info is None:
        return

    device_id = device_info["id"]
    coordinator = hass.data[DOMAIN][account_id].get(DATA_INTELLIGENT_COORDINATOR_KEY.format(device_id))
    if coordinator is None:
        return

    async_add_entities([
        EDFEnergyIntelligentTargetTime(hass, coordinator, account_id, device_info),
    ])


class EDFEnergyIntelligentTargetTime(CoordinatorEntity, EDFEnergyIntelligentDevice, TimeEntity):
    """TIME entity for setting the EV charge ready-by time."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str, device_info: dict):
        self._device_id = device_info["id"]
        EDFEnergyIntelligentDevice.__init__(
            self, hass, account_id, self._device_id,
            device_info.get("make"), device_info.get("model"), device_info.get("device_type"),
        )
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._device_id}_intelligent_target_time_input"

    @property
    def name(self):
        return f"EDF Intelligent Target Time Input ({self._account_id})"

    @property
    def icon(self):
        return "mdi:clock-time-four-outline"

    @property
    def native_value(self) -> time | None:
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is not None and result.target_time is not None:
            raw = str(result.target_time)[:5]  # "HH:MM"
            try:
                parts = raw.split(":")
                return time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass
        return time(7, 0)

    @callback
    def _handle_coordinator_update(self) -> None:
        super()._handle_coordinator_update()

    async def async_set_value(self, value: time) -> None:
        client = self.hass.data[DOMAIN][self._account_id][DATA_CLIENT]
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        target_pct = result.target_percentage if result and result.target_percentage is not None else DEFAULT_TARGET_PCT
        time_str = value.strftime("%H:%M")
        await client.async_set_intelligent_preferences(self._device_id, int(target_pct), time_str)
        await self.coordinator.async_request_refresh()
