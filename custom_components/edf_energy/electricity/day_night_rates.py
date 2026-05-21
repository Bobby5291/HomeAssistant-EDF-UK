# Bobby5291 2026 — EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.dt import now, as_utc
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass

from .base import EDFEnergyElectricitySensor
from ..utils.attributes import dict_to_typed_dict
from ..coordinators.electricity_rates import ElectricityRatesCoordinatorResult

_LOGGER = logging.getLogger(__name__)


def _get_day_night_rates(rates: list, current):
    """Return (day_rate, night_rate) from today's rate list. day=max, night=min."""
    if not rates:
        return None, None

    today_start = as_utc(current.replace(hour=0, minute=0, second=0, microsecond=0))
    today_end = as_utc(current.replace(hour=23, minute=59, second=59, microsecond=999999))

    today_values = [
        r["value_inc_vat"]
        for r in rates
        if r["start"] >= today_start and r["start"] <= today_end
    ]

    if not today_values:
        return None, None

    unique_values = list(set(today_values))
    return max(unique_values), min(unique_values)


class EDFEnergyElectricityDayRate(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """
    The peak (day) electricity unit rate for today.
    For flat-rate tariffs this equals the single rate.
    For Economy 7 / day-night tariffs this is the higher (day) rate.
    """

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._attributes.update({
            "tariff_code": None,
            "night_rate": None,
            "is_economy_7": None,
        })

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_day_rate'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Day Rate ({self._serial_number}/{self._mpan})'

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def device_class(self):
        return SensorDeviceClass.MONETARY

    @property
    def icon(self):
        return "mdi:weather-sunny"

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
        rates_result: ElectricityRatesCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )

        if rates_result is not None and rates_result.rates:
            day_rate, night_rate = _get_day_night_rates(rates_result.rates, current)
            self._state = day_rate
            tariff_code = rates_result.rates[0].get("tariff_code") if rates_result.rates else None
            self._attributes.update({
                "tariff_code": tariff_code,
                "night_rate": night_rate,
                "is_economy_7": (night_rate is not None and day_rate != night_rate),
            })
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
            _LOGGER.debug(f'Restored EDFEnergyElectricityDayRate state: {self._state}')


class EDFEnergyElectricityNightRate(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """
    The off-peak (night) electricity unit rate for today.
    For flat-rate tariffs this equals the day rate.
    For Economy 7 / day-night tariffs this is the lower (night) rate.
    """

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._attributes.update({
            "tariff_code": None,
            "day_rate": None,
            "is_economy_7": None,
        })

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_night_rate'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Night Rate ({self._serial_number}/{self._mpan})'

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def device_class(self):
        return SensorDeviceClass.MONETARY

    @property
    def icon(self):
        return "mdi:weather-night"

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
        rates_result: ElectricityRatesCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )

        if rates_result is not None and rates_result.rates:
            day_rate, night_rate = _get_day_night_rates(rates_result.rates, current)
            self._state = night_rate
            tariff_code = rates_result.rates[0].get("tariff_code") if rates_result.rates else None
            self._attributes.update({
                "tariff_code": tariff_code,
                "day_rate": day_rate,
                "is_economy_7": (night_rate is not None and day_rate != night_rate),
            })
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
            _LOGGER.debug(f'Restored EDFEnergyElectricityNightRate state: {self._state}')
