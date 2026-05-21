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
from ..statistics.consumption import (
    async_import_consumption_statistics,
    electricity_consumption_statistic_id,
    electricity_consumption_statistic_name,
)
from ..statistics.cost import (
    async_import_cost_statistics,
    electricity_cost_statistic_id,
    electricity_cost_statistic_name,
)

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
        return True

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
            from homeassistant.util.dt import now as ha_now
            from homeassistant.const import UnitOfEnergy as _UOE
            self._hass.async_create_task(
                async_import_consumption_statistics(
                    self._hass,
                    ha_now(),
                    electricity_consumption_statistic_id(self._serial_number, self._mpan, self._is_export),
                    electricity_consumption_statistic_name(self._serial_number, self._mpan, self._is_export),
                    consumption_data,
                    rate_data,
                    _UOE.KILO_WATT_HOUR,
                )
            )
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
        return True

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
            from homeassistant.util.dt import now as ha_now
            self._hass.async_create_task(
                async_import_cost_statistics(
                    self._hass,
                    ha_now(),
                    electricity_cost_statistic_id(self._serial_number, self._mpan, self._is_export),
                    electricity_cost_statistic_name(self._serial_number, self._mpan, self._is_export),
                    consumption_data,
                    rate_data,
                )
            )
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


def calculate_electricity_peak_offpeak(consumption_data: list, rate_data: list, standing_charge: float):
    """
    Split yesterday's consumption + cost into peak (day) and off-peak (night) buckets.
    For single-rate tariffs all consumption is classified as peak.
    Returns dict or None.
    """
    if not consumption_data or not rate_data:
        return None

    all_rate_values = list(set(r["value_inc_vat"] for r in rate_data))
    is_economy_7 = len(all_rate_values) > 1
    peak_threshold = max(all_rate_values)

    peak_kwh = 0.0
    peak_pence = 0.0
    offpeak_kwh = 0.0
    offpeak_pence = 0.0
    matched = False

    for item in consumption_data:
        kwh = item["consumption"]
        matched_rate = None
        for rate in rate_data:
            if rate["start"] <= item["start"] < rate["end"]:
                matched_rate = rate
                break
        if matched_rate is None:
            continue

        matched = True
        rate_pence = matched_rate["value_inc_vat"]
        cost_pence = consumption_cost_in_pence(kwh, rate_pence)

        if not is_economy_7 or rate_pence >= peak_threshold:
            peak_kwh += kwh
            peak_pence += cost_pence
        else:
            offpeak_kwh += kwh
            offpeak_pence += cost_pence

    if not matched:
        return None

    standing_charge_pounds = pence_to_pounds_pence(standing_charge) if standing_charge is not None else 0

    return {
        "is_economy_7": is_economy_7,
        "peak_consumption": round(peak_kwh, 5),
        "peak_cost": pence_to_pounds_pence(peak_pence),
        "offpeak_consumption": round(offpeak_kwh, 5),
        "offpeak_cost": pence_to_pounds_pence(offpeak_pence),
        "standing_charge": standing_charge_pounds,
        "last_reset": consumption_data[-1]["end"],
    }


class EDFEnergyPreviousElectricityPeakConsumption(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Yesterday's peak (day-rate) electricity consumption in kWh."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._last_reset = None

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_previous_peak_consumption'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Previous Peak Consumption ({self._serial_number}/{self._mpan})'

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
        return "mdi:weather-sunny"

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

        result: PreviousConsumptionCoordinatorResult = (
            self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None
        )
        split = calculate_electricity_peak_offpeak(
            result.consumption if result else None,
            result.rates if result else None,
            result.standing_charge if result else None,
        )
        if split is not None:
            self._state = split["peak_consumption"]
            self._last_reset = split["last_reset"]
            self._attributes.update({
                "is_economy_7": split["is_economy_7"],
                "offpeak_consumption": split["offpeak_consumption"],
            })
        self._attributes = dict_to_typed_dict(self._attributes)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)


class EDFEnergyPreviousElectricityOffPeakConsumption(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Yesterday's off-peak (night-rate) electricity consumption in kWh."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._last_reset = None

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_previous_offpeak_consumption'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Previous Off-Peak Consumption ({self._serial_number}/{self._mpan})'

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
        return "mdi:weather-night"

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

        result: PreviousConsumptionCoordinatorResult = (
            self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None
        )
        split = calculate_electricity_peak_offpeak(
            result.consumption if result else None,
            result.rates if result else None,
            result.standing_charge if result else None,
        )
        if split is not None:
            self._state = split["offpeak_consumption"]
            self._last_reset = split["last_reset"]
            self._attributes.update({
                "is_economy_7": split["is_economy_7"],
                "peak_consumption": split["peak_consumption"],
            })
        self._attributes = dict_to_typed_dict(self._attributes)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)


class EDFEnergyPreviousElectricityPeakCost(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Yesterday's peak-rate electricity cost in GBP."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._last_reset = None

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_previous_peak_cost'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Previous Peak Cost ({self._serial_number}/{self._mpan})'

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

        result: PreviousConsumptionCoordinatorResult = (
            self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None
        )
        split = calculate_electricity_peak_offpeak(
            result.consumption if result else None,
            result.rates if result else None,
            result.standing_charge if result else None,
        )
        if split is not None:
            self._state = split["peak_cost"]
            self._last_reset = split["last_reset"]
            self._attributes.update({
                "is_economy_7": split["is_economy_7"],
                "offpeak_cost": split["offpeak_cost"],
                "standing_charge": split["standing_charge"],
            })
        self._attributes = dict_to_typed_dict(self._attributes)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)


class EDFEnergyPreviousElectricityOffPeakCost(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Yesterday's off-peak-rate electricity cost in GBP."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._last_reset = None

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_previous_offpeak_cost'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Previous Off-Peak Cost ({self._serial_number}/{self._mpan})'

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

        result: PreviousConsumptionCoordinatorResult = (
            self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None
        )
        split = calculate_electricity_peak_offpeak(
            result.consumption if result else None,
            result.rates if result else None,
            result.standing_charge if result else None,
        )
        if split is not None:
            self._state = split["offpeak_cost"]
            self._last_reset = split["last_reset"]
            self._attributes.update({
                "is_economy_7": split["is_economy_7"],
                "peak_cost": split["peak_cost"],
            })
        self._attributes = dict_to_typed_dict(self._attributes)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
