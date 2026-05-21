# Bobby5291 2026 — EDF Energy / Kraken API — EV target time and rate mode selects

import logging

from homeassistant.components.select import SelectEntity
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

# 48 half-hour increments across the day
_TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]

DEFAULT_TARGET_PERCENTAGE = 80


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up EDF Energy intelligent select entities."""
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
        EDFEnergyIntelligentTargetTimeSelect(hass, coordinator, account_id, device_info),
        EDFEnergyIntelligentRateModeSelect(hass, coordinator, account_id, device_info),
    ])


class _IntelligentSelectBase(CoordinatorEntity, EDFEnergyIntelligentDevice, SelectEntity):

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str, device_info: dict):
        self._device_id = device_info["id"]
        EDFEnergyIntelligentDevice.__init__(
            self, hass, account_id, self._device_id,
            device_info.get("make"), device_info.get("model"), device_info.get("device_type")
        )
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def extra_state_attributes(self):
        return self._attributes


class EDFEnergyIntelligentTargetTimeSelect(_IntelligentSelectBase):
    """Select entity for the EV ready-by target time."""

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._device_id}_intelligent_target_time"

    @property
    def name(self):
        return f"EDF Intelligent Target Time ({self._account_id})"

    @property
    def icon(self):
        return "mdi:clock-outline"

    @property
    def options(self):
        return _TIME_OPTIONS

    @property
    def current_option(self):
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is not None and result.target_time is not None:
            # Normalise "HH:MM:SS" → "HH:MM"
            t = str(result.target_time)[:5]
            if t in _TIME_OPTIONS:
                return t
        return "07:00"

    @callback
    def _handle_coordinator_update(self) -> None:
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        client = self.hass.data[DOMAIN][self._account_id][DATA_CLIENT]
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        target_pct = result.target_percentage if result and result.target_percentage is not None else DEFAULT_TARGET_PERCENTAGE
        await client.async_set_intelligent_preferences(self._device_id, int(target_pct), option)
        await self.coordinator.async_request_refresh()


class EDFEnergyIntelligentRateModeSelect(_IntelligentSelectBase):
    """Select entity for smart/manual rate mode (suspend/unsuspend smart charge)."""

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._device_id}_intelligent_rate_mode"

    @property
    def name(self):
        return f"EDF Intelligent Rate Mode ({self._account_id})"

    @property
    def icon(self):
        return "mdi:sine-wave"

    @property
    def options(self):
        return ["smart", "manual"]

    @property
    def current_option(self):
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is not None:
            return "manual" if result.is_suspended else "smart"
        return "smart"

    @callback
    def _handle_coordinator_update(self) -> None:
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is not None:
            self._attributes = {
                "current_state": result.current_state,
                "is_suspended": result.is_suspended,
            }
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        client = self.hass.data[DOMAIN][self._account_id][DATA_CLIENT]
        suspend = option == "manual"
        await client.async_set_intelligent_smart_control(self._device_id, suspend=suspend)
        await self.coordinator.async_request_refresh()
