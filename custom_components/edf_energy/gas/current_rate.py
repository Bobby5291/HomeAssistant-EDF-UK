# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.dt import now
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass

from .base import EDFEnergyGasSensor
from ..utils.attributes import dict_to_typed_dict
from ..utils.rate_information import get_current_rate_information
from ..coordinators.gas_rates import GasRatesCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class EDFEnergyGasCurrentRate(CoordinatorEntity, EDFEnergyGasSensor, RestoreSensor):
    """Sensor for displaying the current gas rate."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyGasSensor.__init__(self, hass, meter, point)

        self._state = None
        self._attributes.update({
            "tariff": None,
            "start": None,
            "end": None,
            "current_day_min_rate": None,
            "current_day_max_rate": None,
            "current_day_average_rate": None,
        })

    @property
    def unique_id(self):
        return f'edf_energy_gas_{self._serial_number}_{self._mprn}_current_rate'

    @property
    def name(self):
        return f'EDF Gas Current Rate ({self._serial_number}/{self._mprn})'

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
        rates_result: GasRatesCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None

        if rates_result is not None:
            _LOGGER.debug(f"Updating EDFEnergyGasCurrentRate for '{self._mprn}/{self._serial_number}'")
            rate_information = get_current_rate_information(rates_result.rates, current)

            if rate_information is not None:
                self._state = rate_information["current_rate"]["value_inc_vat"]
                self._attributes.update({
                    "tariff": rate_information["current_rate"]["tariff_code"],
                    "start": rate_information["current_rate"]["start"],
                    "end": rate_information["current_rate"]["end"],
                    "current_day_min_rate": rate_information["min_rate_today"],
                    "current_day_max_rate": rate_information["max_rate_today"],
                    "current_day_average_rate": rate_information["average_rate_today"],
                    "all_rates": rate_information["all_rates"],
                    "applicable_rates": rate_information["applicable_rates"],
                })
            else:
                self._state = None
                self._attributes.update({
                    "tariff": None, "start": None, "end": None,
                    "current_day_min_rate": None,
                    "current_day_max_rate": None, "current_day_average_rate": None,
                })

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes, ['all_rates', 'applicable_rates'])
            _LOGGER.debug(f'Restored EDFEnergyGasCurrentRate state: {self._state}')
