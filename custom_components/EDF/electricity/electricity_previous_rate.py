# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 [year] — adapted for EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.dt import now
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass

from .base import EDFEnergyElectricitySensor
from ..utils.attributes import dict_to_typed_dict
from ..utils.rate_information import get_previous_rate_information
from ..coordinators.electricity_rates import ElectricityRatesCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class EDFEnergyElectricityPreviousRate(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Sensor for displaying the previous electricity rate."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._attributes.update({"start": None, "end": None})

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_previous_rate'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Previous Rate ({self._serial_number}/{self._mpan})'

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
        return "GBP/kWh"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        current = now()
        rates_result: ElectricityRatesCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None

        if rates_result is not None:
            rate_information = get_previous_rate_information(rates_result.rates, current)

            if rate_information is not None:
                self._state = rate_information["previous_rate"]["value_inc_vat"]
                self._attributes["start"] = rate_information["previous_rate"]["start"]
                self._attributes["end"] = rate_information["previous_rate"]["end"]
            else:
                self._state = None
                self._attributes["start"] = None
                self._attributes["end"] = None

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
            _LOGGER.debug(f'Restored EDFEnergyElectricityPreviousRate state: {self._state}')
