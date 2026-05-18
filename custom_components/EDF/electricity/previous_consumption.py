# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 [year] — adapted for EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass

from .base import EDFEnergyElectricitySensor
from ..utils.attributes import dict_to_typed_dict
from ..utils.conversions import consumption_cost_in_pence, pence_to_pounds_pence
from ..coordinators.previous_consumption_and_rates import PreviousConsumptionCoordinatorResult

_LOGGER = logging.getLogger(__name__)


def calculate_electricity_consumption_and_cost(
    consumption_data: list,
    rate_data: list,
    standing_charge: float,
    last_reset,
):
    """Calculate total consumption and cost from half-hourly data."""
    if consumption_data is None or rate_data is None:
        return None

    total_consumption = 0
    total_cost_pence = 0
    charges = []

    for consumption in consumption_data:
        current_rate = None
        for rate in rate_data:
            if rate["start"] <= consumption["start"] < rate["end"]:
                current_rate = rate
                break

        if current_rate is None:
            continue

        consumption_kwh = consumption["consumption"]
        rate_pence = current_rate["value_inc_vat"]
        cost_pence = consumption_cost_in_pence(consumption_kwh, rate_pence)

        total_consumption += consumption_kwh
        total_cost_pence += cost_pence

        charges.append({
            "start": consumption["start"],
            "end": consumption["end"],
            "consumption": consumption_kwh,
            "rate": pence_to_pounds_pence(rate_pence),
            "cost": pence_to_pounds_pence(cost_pence),
        })

    if len(charges) == 0:
        return None

    standing_charge_pounds = pence_to_pounds_pence(standing_charge) if standing_charge is not None else 0
    total_cost_pounds = pence_to_pounds_pence(total_cost_pence)

    return {
        "total_consumption": round(total_consumption, 5),
        "total_cost_without_standing_charge": total_cost_pounds,
        "total_cost": round(total_cost_pounds + standing_charge_pounds, 2),
        "standing_charge": standing_charge_pounds,
        "last_reset": consumption_data[-1]["end"],
        "charges": charges,
    }


class EDFEnergyPreviousAccumulativeElectricityConsumption(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Sensor for displaying yesterday's total electricity consumption."""

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
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_previous_accumulative_consumption'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Previous Accumulative Consumption ({self._serial_number}/{self._mpan})'

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

    @property
    def should_poll(self):
        return True

    async def async_update(self):
        await super().async_update()

        if not self.enabled:
            return

        result: PreviousConsumptionCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None
        consumption_data = result.consumption if result is not None else None
        rate_data = result.rates if result is not None else None
        standing_charge = result.standing_charge if result is not None else None

        consumption_and_cost = calculate_electricity_consumption_and_cost(
            consumption_data,
            rate_data,
            standing_charge,
            self._last_reset,
        )

        if consumption_and_cost is not None:
            _LOGGER.debug(f"Calculated previous electricity consumption for '{self._mpan}/{self._serial_number}'")
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
        else:
            _LOGGER.debug(f"No consumption data available for '{self._mpan}/{self._serial_number}'")

        self._attributes = dict_to_typed_dict(self._attributes)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
            _LOGGER.debug(f'Restored EDFEnergyPreviousAccumulativeElectricityConsumption state: {self._state}')


class EDFEnergyPreviousAccumulativeElectricityCost(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Sensor for displaying yesterday's total electricity cost."""

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
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_previous_accumulative_cost'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Previous Accumulative Cost ({self._serial_number}/{self._mpan})'

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

    @property
    def should_poll(self):
        return True

    async def async_update(self):
        await super().async_update()

        if not self.enabled:
            return

        result: PreviousConsumptionCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None
        consumption_data = result.consumption if result is not None else None
        rate_data = result.rates if result is not None else None
        standing_charge = result.standing_charge if result is not None else None

        consumption_and_cost = calculate_electricity_consumption_and_cost(
            consumption_data,
            rate_data,
            standing_charge,
            self._last_reset,
        )

        if consumption_and_cost is not None:
            _LOGGER.debug(f"Calculated previous electricity cost for '{self._mpan}/{self._serial_number}'")
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
        else:
            _LOGGER.debug(f"No cost data available for '{self._mpan}/{self._serial_number}'")

        self._attributes = dict_to_typed_dict(self._attributes)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
            _LOGGER.debug(f'Restored EDFEnergyPreviousAccumulativeElectricityCost state: {self._state}')
