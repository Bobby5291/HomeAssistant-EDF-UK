# Bobby5291 2026 — EDF Energy / Kraken API — Intelligent EV binary sensor

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import now as ha_now

from . import EDFEnergyIntelligentDevice
from ..coordinators.intelligent import IntelligentCoordinatorResult

_LOGGER = logging.getLogger(__name__)

_OFF_PEAK_STATES = {"SMART_CONTROL_IN_PROGRESS", "BOOSTING"}


class EDFEnergyIntelligentOffPeakBinarySensor(CoordinatorEntity, EDFEnergyIntelligentDevice, BinarySensorEntity, RestoreEntity):
    """Binary sensor that is ON when the EV is currently in a smart (off-peak) charge window."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str, device_info: dict):
        self._device_id = device_info["id"]
        EDFEnergyIntelligentDevice.__init__(
            self, hass, account_id, self._device_id,
            device_info.get("make"), device_info.get("model"), device_info.get("device_type")
        )
        CoordinatorEntity.__init__(self, coordinator)
        self._state = False

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._device_id}_intelligent_off_peak"

    @property
    def name(self):
        return f"EDF Intelligent Off Peak ({self._account_id})"

    @property
    def icon(self):
        return "mdi:battery-charging-low"

    @property
    def is_on(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is not None:
            current = ha_now()
            in_dispatch = any(
                d["start"] <= current <= d["end"]
                for d in result.planned_dispatches
            )
            in_state = result.current_state in _OFF_PEAK_STATES
            self._state = in_dispatch or in_state
            self._attributes = {
                "current_state": result.current_state,
                "planned_dispatch_active": in_dispatch,
            }
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._state = state.state.lower() == "on"
