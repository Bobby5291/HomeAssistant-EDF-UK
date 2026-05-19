# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .base import EDFEnergyGasSensor
from ..utils.attributes import dict_to_typed_dict
from ..coordinators.gas_standing_charges import GasStandingChargeCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class EDFEnergyGasCurrentStandingCharge(CoordinatorEntity, EDFEnergyGasSensor, RestoreSensor):
    """Sensor for displaying the current gas standing charge."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyGasSensor.__init__(self, hass, meter, point)
        self._state = None

    @property
    def unique_id(self):
        return f'edf_energy_gas_{self._serial_number}_{self._mprn}_current_standing_charge'

    @property
    def name(self):
        return f'EDF Gas Standing Charge ({self._serial_number}/{self._mprn})'

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def device_class(self):
        return SensorDeviceClass.MONETARY

    @property
    def icon(self):
        return "mdi:currency-gbp"

    @property
    def native_unit_of_measurement(self):
        return "GBP"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        result: GasStandingChargeCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None

        if result is not None and result.standing_charge is not None:
            self._state = result.standing_charge["value_inc_vat"] / 100
            self._attributes["start"] = result.standing_charge["start"]
            self._attributes["end"] = result.standing_charge["end"]
            self._attributes["tariff_code"] = result.standing_charge["tariff_code"]
        else:
            self._state = None

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
            _LOGGER.debug(f'Restored EDFEnergyGasCurrentStandingCharge state: {self._state}')
