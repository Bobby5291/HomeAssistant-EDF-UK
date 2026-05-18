# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.dt import now
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass

from .base import EDFEnergyElectricitySensor
from . import calculate_electricity_consumption_and_cost
from ..coordinators import MultiCoordinatorEntity
from ..coordinators.current_consumption import CurrentConsumptionCoordinatorResult
from ..utils.attributes import dict_to_typed_dict
from ..utils.consumption import calculate_current_consumption

_LOGGER = logging.getLogger(__name__)


class EDFEnergyCurrentElectricityConsumption(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Sensor for the current half-hourly electricity consumption delta."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._latest_date = None
        self._previous_total_consumption = None
        self._last_evaluated = None

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}_current_consumption'

    @property
    def name(self):
        return f'EDF Electricity Current Consumption ({self._serial_number}/{self._mpan})'

    @property
    def device_class(self):
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def native_unit_of_measurement(self):
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def icon(self):
        return "mdi:lightning-bolt"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def last_reset(self):
        return self._latest_date

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        consumption_result: CurrentConsumptionCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None
        current_date = now()

        result = calculate_current_consumption(
            current_date,
            consumption_result,
            self._state,
            self._last_evaluated if self._last_evaluated is not None else current_date,
            self._previous_total_consumption,
        )

        self._state = result.state
        self._latest_date = result.last_evaluated
        self._previous_total_consumption = result.total_consumption
        self._last_evaluated = result.last_evaluated

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
            self._attributes.pop("last_updated_timestamp", None)
            self._attributes.pop("last_reset", None)
            _LOGGER.debug(f'Restored EDFEnergyCurrentElectricityConsumption state: {self._state}')


class EDFEnergyCurrentElectricityDemand(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Sensor for the current live electricity demand in watts."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}_current_demand'

    @property
    def name(self):
        return f'EDF Electricity Current Demand ({self._serial_number}/{self._mpan})'

    @property
    def device_class(self):
        return SensorDeviceClass.POWER

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self):
        return "W"

    @property
    def icon(self):
        return "mdi:lightning-bolt"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        consumption_result: CurrentConsumptionCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None
        consumption_data = consumption_result.data if consumption_result is not None else None

        if consumption_data is not None and len(consumption_data) > 0:
            self._state = consumption_data[-1]["demand"]

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
            self._attributes.pop("last_updated_timestamp", None)
            _LOGGER.debug(f'Restored EDFEnergyCurrentElectricityDemand state: {self._state}')


class EDFEnergyCurrentTotalElectricityConsumption(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Sensor for the cumulative total electricity consumption today (kWh)."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._last_reset = None

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self._is_smart_meter

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}_current_total_consumption'

    @property
    def name(self):
        return f'EDF Electricity Current Total Consumption ({self._serial_number}/{self._mpan})'

    @property
    def device_class(self):
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self):
        return SensorStateClass.TOTAL_INCREASING

    @property
    def native_unit_of_measurement(self):
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def icon(self):
        return "mdi:lightning-bolt"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        consumption_result: CurrentConsumptionCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None
        consumption_data = consumption_result.data if consumption_result is not None else None

        if consumption_data is not None and len(consumption_data) > 0:
            total = consumption_data[-1]["total_consumption"]
            if total is not None and total != 0:
                self._state = total
                self._last_reset = now()

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
            _LOGGER.debug(f'Restored EDFEnergyCurrentTotalElectricityConsumption state: {self._state}')


class EDFEnergyCurrentAccumulativeElectricityConsumption(MultiCoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Sensor for today's accumulative electricity consumption with cost calculation."""

    def __init__(self, hass: HomeAssistant, coordinator, rates_coordinator, standing_charge_coordinator, meter, point):
        MultiCoordinatorEntity.__init__(self, coordinator, [rates_coordinator, standing_charge_coordinator])
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._last_reset = None
        self._rates_coordinator = rates_coordinator
        self._standing_charge_coordinator = standing_charge_coordinator

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self._is_smart_meter

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}_current_accumulative_consumption'

    @property
    def name(self):
        return f'EDF Electricity Current Accumulative Consumption ({self._serial_number}/{self._mpan})'

    @property
    def device_class(self):
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def native_unit_of_measurement(self):
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def icon(self):
        return "mdi:lightning-bolt"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def last_reset(self):
        return self._last_reset

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        consumption_result: CurrentConsumptionCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None
        consumption_data = consumption_result.data if consumption_result is not None else None
        rate_data = self._rates_coordinator.data.rates if self._rates_coordinator is not None and self._rates_coordinator.data is not None else None
        standing_charge = self._standing_charge_coordinator.data.standing_charge["value_inc_vat"] if self._standing_charge_coordinator is not None and self._standing_charge_coordinator.data is not None and self._standing_charge_coordinator.data.standing_charge is not None else None

        consumption_and_cost = calculate_electricity_consumption_and_cost(
            consumption_data, rate_data, standing_charge, None
        )

        if consumption_and_cost is not None:
            self._state = consumption_and_cost["total_consumption"]
            self._last_reset = consumption_and_cost["last_reset"]
            self._attributes.update({
                "total": consumption_and_cost["total_consumption"],
                "charges": list(map(lambda c: {
                    "start": c["start"],
                    "end": c["end"],
                    "consumption": c["consumption"],
                }, consumption_and_cost["charges"])),
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
            _LOGGER.debug(f'Restored EDFEnergyCurrentAccumulativeElectricityConsumption state: {self._state}')


class EDFEnergyCurrentAccumulativeElectricityCost(MultiCoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Sensor for today's accumulative electricity cost in GBP."""

    def __init__(self, hass: HomeAssistant, coordinator, rates_coordinator, standing_charge_coordinator, meter, point):
        MultiCoordinatorEntity.__init__(self, coordinator, [rates_coordinator, standing_charge_coordinator])
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._last_reset = None
        self._rates_coordinator = rates_coordinator
        self._standing_charge_coordinator = standing_charge_coordinator

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self._is_smart_meter

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_current_accumulative_cost'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Current Accumulative Cost ({self._serial_number}/{self._mpan})'

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
    def extra_state_attributes(self):
        return self._attributes

    @property
    def last_reset(self):
        return self._last_reset

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        consumption_result: CurrentConsumptionCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None
        consumption_data = consumption_result.data if consumption_result is not None else None
        rate_data = self._rates_coordinator.data.rates if self._rates_coordinator is not None and self._rates_coordinator.data is not None else None
        standing_charge = self._standing_charge_coordinator.data.standing_charge["value_inc_vat"] if self._standing_charge_coordinator is not None and self._standing_charge_coordinator.data is not None and self._standing_charge_coordinator.data.standing_charge is not None else None

        consumption_and_cost = calculate_electricity_consumption_and_cost(
            consumption_data, rate_data, standing_charge, None
        )

        if consumption_and_cost is not None:
            self._state = consumption_and_cost["total_cost"]
            self._last_reset = consumption_and_cost["last_reset"]
            self._attributes.update({
                "tariff_code": rate_data[0]["tariff_code"] if rate_data else None,
                "standing_charge": consumption_and_cost["standing_charge"],
                "total_without_standing_charge": consumption_and_cost["total_cost_without_standing_charge"],
                "total": consumption_and_cost["total_cost"],
                "charges": list(map(lambda c: {
                    "start": c["start"],
                    "end": c["end"],
                    "rate": c["rate"],
                    "consumption": c["consumption"],
                    "cost": c["cost"],
                }, consumption_and_cost["charges"])),
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
            _LOGGER.debug(f'Restored EDFEnergyCurrentAccumulativeElectricityCost state: {self._state}')
