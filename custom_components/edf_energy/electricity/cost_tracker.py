# Bobby5291 2026 — EDF Energy / Kraken API

import logging
from datetime import datetime

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass

from .base import EDFEnergyElectricitySensor
from ..utils.attributes import dict_to_typed_dict
from ..coordinators.consumption_cost_tracker import ConsumptionCostTrackerCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class _ElecCostTrackerBase(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Base for electricity daily/weekly/monthly cost sensors."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._last_reset = None

    @property
    def device_class(self):
        return SensorDeviceClass.MONETARY

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def native_unit_of_measurement(self):
        return "GBP"

    @property
    def icon(self):
        return "mdi:currency-gbp"

    @property
    def native_value(self):
        return self._state

    @property
    def last_reset(self):
        return self._last_reset

    @property
    def extra_state_attributes(self):
        return self._attributes

    def _extract(self, result: ConsumptionCostTrackerCoordinatorResult):
        """Subclasses return (consumption, cost, reset) from result."""
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        result: ConsumptionCostTrackerCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        if result is not None:
            consumption, cost, reset = self._extract(result)
            self._state = cost
            self._last_reset = reset
            self._attributes.update({
                "consumption_kwh": consumption,
                "cost_gbp": cost,
                "period_start": reset,
            })
        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)


class EDFEnergyElectricityDailyCost(_ElecCostTrackerBase):
    """Cost so far today for electricity (consumption cost + 1 day standing charge)."""

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_daily_cost'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Daily Cost ({self._serial_number}/{self._mpan})'

    def _extract(self, result):
        return result.daily_consumption, result.daily_cost, result.daily_reset


class EDFEnergyElectricityWeeklyCost(_ElecCostTrackerBase):
    """Cost so far this week for electricity (Mon–now)."""

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_weekly_cost'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Weekly Cost ({self._serial_number}/{self._mpan})'

    def _extract(self, result):
        return result.weekly_consumption, result.weekly_cost, result.weekly_reset


class EDFEnergyElectricityMonthlyCost(_ElecCostTrackerBase):
    """Cost so far this month for electricity (1st–now)."""

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_monthly_cost'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Monthly Cost ({self._serial_number}/{self._mpan})'

    def _extract(self, result):
        return result.monthly_consumption, result.monthly_cost, result.monthly_reset
