# Bobby5291 2026 — EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass

from .base import EDFEnergyGasSensor
from ..utils.attributes import dict_to_typed_dict

_LOGGER = logging.getLogger(__name__)


class _GasDiagnosticBase(CoordinatorEntity, EDFEnergyGasSensor, RestoreSensor):
    """Base: last-retrieved timestamp diagnostic for gas coordinators."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyGasSensor.__init__(self, hass, meter, point)
        self._state = None

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
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        result = (
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


class EDFEnergyGasRatesLastRetrieved(_GasDiagnosticBase):
    @property
    def unique_id(self):
        return f'edf_energy_gas_{self._serial_number}_{self._mprn}_rates_last_retrieved'

    @property
    def name(self):
        return f'EDF Gas Rates Last Retrieved ({self._serial_number}/{self._mprn})'

    @property
    def icon(self):
        return "mdi:clock-check"


class EDFEnergyGasStandingChargeLastRetrieved(_GasDiagnosticBase):
    @property
    def unique_id(self):
        return f'edf_energy_gas_{self._serial_number}_{self._mprn}_standing_charge_last_retrieved'

    @property
    def name(self):
        return f'EDF Gas Standing Charge Last Retrieved ({self._serial_number}/{self._mprn})'

    @property
    def icon(self):
        return "mdi:clock-check"


class EDFEnergyGasConsumptionLastRetrieved(_GasDiagnosticBase):
    @property
    def unique_id(self):
        return f'edf_energy_gas_{self._serial_number}_{self._mprn}_consumption_last_retrieved'

    @property
    def name(self):
        return f'EDF Gas Consumption Last Retrieved ({self._serial_number}/{self._mprn})'

    @property
    def icon(self):
        return "mdi:clock-check"
