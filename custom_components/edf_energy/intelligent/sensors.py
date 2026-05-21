# Bobby5291 2026 — EDF Energy / Kraken API — Intelligent EV sensor entities

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EDFEnergyIntelligentDevice
from ..coordinators.intelligent import IntelligentCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class EDFEnergyIntelligentCurrentStateSensor(CoordinatorEntity, EDFEnergyIntelligentDevice, RestoreEntity):
    """Sensor showing the EV device's current SmartFlex state."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str, device_info: dict):
        self._device_id = device_info["id"]
        EDFEnergyIntelligentDevice.__init__(
            self, hass, account_id, self._device_id,
            device_info.get("make"), device_info.get("model"), device_info.get("device_type")
        )
        CoordinatorEntity.__init__(self, coordinator)
        self._state = None

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._device_id}_intelligent_current_state"

    @property
    def name(self):
        return f"EDF Intelligent Current State ({self._account_id})"

    @property
    def icon(self):
        return "mdi:ev-station"

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is not None:
            self._state = result.current_state
            self._attributes = {
                "is_suspended": result.is_suspended,
                "is_bump_charging": result.is_bump_charging,
                "target_percentage": result.target_percentage,
                "target_time": result.target_time,
                "mode": result.mode,
            }
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._state = state.state


class EDFEnergyIntelligentDispatchesLastRetrieved(CoordinatorEntity, EDFEnergyIntelligentDevice):
    """Diagnostic sensor — timestamp when dispatches were last fetched from EDF."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str, device_info: dict):
        self._device_id = device_info["id"]
        EDFEnergyIntelligentDevice.__init__(
            self, hass, account_id, self._device_id,
            device_info.get("make"), device_info.get("model"), device_info.get("device_type")
        )
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._device_id}_intelligent_dispatches_last_retrieved"

    @property
    def name(self):
        return f"EDF Intelligent Dispatches Last Retrieved ({self._account_id})"

    @property
    def device_class(self):
        return SensorDeviceClass.TIMESTAMP

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def entity_registry_enabled_default(self):
        return False

    @property
    def native_value(self):
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is not None:
            return result.last_retrieved
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        super()._handle_coordinator_update()
