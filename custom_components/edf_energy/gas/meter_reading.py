# Bobby5291 2026 — EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass

from .base import EDFEnergyGasSensor
from ..utils.attributes import dict_to_typed_dict
from ..coordinators.gas_meter_readings import GasMeterReadingsCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class EDFEnergyGasMeterReading(CoordinatorEntity, EDFEnergyGasSensor, RestoreSensor):
    """
    Latest gas meter register reading in m³.
    This is the actual cumulative register value displayed on the meter.
    """

    def __init__(self, hass: HomeAssistant, coordinator, meter: dict, point: dict):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyGasSensor.__init__(self, hass, meter, point)
        self._state = None
        self._attributes.update({"read_at": None})

    @property
    def unique_id(self):
        return f'edf_energy_gas_{self._serial_number}_{self._mprn}_meter_reading'

    @property
    def name(self):
        return f'EDF Gas Meter Reading ({self._serial_number}/{self._mprn})'

    @property
    def device_class(self):
        return SensorDeviceClass.GAS

    @property
    def state_class(self):
        return SensorStateClass.TOTAL_INCREASING

    @property
    def native_unit_of_measurement(self):
        return "m³"

    @property
    def icon(self):
        return "mdi:meter-gas"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        result: GasMeterReadingsCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        if result is not None and result.value is not None:
            self._state = result.value
            self._attributes["read_at"] = result.read_at
        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
            _LOGGER.debug(f'Restored EDFEnergyGasMeterReading state: {self._state}')
