# Bobby5291 2026 — EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory, generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass

from .balance import EDFEnergyAccountSensor
from ..coordinators.account import AccountCoordinatorResult
from ..utils.attributes import dict_to_typed_dict

_LOGGER = logging.getLogger(__name__)


class EDFEnergyAccountLastRetrieved(CoordinatorEntity, EDFEnergyAccountSensor, RestoreSensor):
    """Diagnostic timestamp: when the account data was last fetched from EDF."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = None

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_account_last_retrieved"

    @property
    def name(self):
        return f"EDF Account Last Retrieved ({self._account_id})"

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    @property
    def device_class(self):
        return SensorDeviceClass.TIMESTAMP

    @property
    def icon(self):
        return "mdi:clock-check"

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AccountCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        if result is not None:
            self._state = result.last_retrieved
        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            _LOGGER.debug(f'Restored EDFEnergyAccountLastRetrieved state: {self._state}')
