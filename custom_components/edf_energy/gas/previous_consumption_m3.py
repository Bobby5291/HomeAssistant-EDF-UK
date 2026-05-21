# Bobby5291 2026 — EDF Energy / Kraken API — Gas previous consumption in m³

import logging

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .base import EDFEnergyGasSensor
from ..utils.attributes import dict_to_typed_dict
from ..coordinators.previous_consumption_and_rates import PreviousConsumptionCoordinatorResult
from ..statistics.consumption import (
    async_import_consumption_statistics,
    gas_consumption_statistic_id,
    gas_consumption_statistic_name,
)

_LOGGER = logging.getLogger(__name__)

# Standard calorific value and volume correction factor used by UK gas suppliers
_CALORIFIC_VALUE = 39.5  # MJ/m³  (typical UK network value)
_VOLUME_CORRECTION = 1.02264  # dimensionless
_JOULES_PER_KWH = 3.6


def kwh_to_m3(kwh: float) -> float:
    """Convert kWh to cubic metres using standard UK gas conversion factors."""
    return (kwh * _JOULES_PER_KWH) / (_CALORIFIC_VALUE * _VOLUME_CORRECTION)


class EDFEnergyPreviousAccumulativeGasConsumptionM3(CoordinatorEntity, EDFEnergyGasSensor, RestoreSensor):
    """Previous day gas consumption expressed in cubic metres (m³)."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyGasSensor.__init__(self, hass, meter, point)
        self._state = None
        self._last_reset = None

    @property
    def unique_id(self):
        return f"edf_energy_gas_{self._serial_number}_{self._mprn}_previous_accumulative_consumption_m3"

    @property
    def name(self):
        return f"EDF Gas Previous Accumulative Consumption m³ ({self._serial_number}/{self._mprn})"

    @property
    def device_class(self):
        return SensorDeviceClass.GAS

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def native_unit_of_measurement(self):
        return UnitOfVolume.CUBIC_METERS

    @property
    def icon(self):
        return "mdi:fire"

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
        consumption_data = result.consumption if result is not None else None
        rate_data = result.rates if result is not None else None

        if consumption_data is None or len(consumption_data) == 0:
            _LOGGER.debug(f"No gas consumption data available for '{self._mprn}/{self._serial_number}' (m³)")
            return

        total_m3 = sum(kwh_to_m3(c["consumption"]) for c in consumption_data)
        self._state = round(total_m3, 5)
        self._last_reset = consumption_data[-1]["end"]

        m3_consumption = [
            {
                "start": c["start"],
                "end": c["end"],
                "consumption": round(kwh_to_m3(c["consumption"]), 5),
            }
            for c in consumption_data
        ]
        self._attributes.update({
            "total": self._state,
            "charges": m3_consumption,
        })

        from homeassistant.util.dt import now as ha_now
        # Convert consumption records to m³ for statistics
        m3_records = [
            {**c, "consumption": kwh_to_m3(c["consumption"])} for c in consumption_data
        ]
        self._hass.async_create_task(
            async_import_consumption_statistics(
                self._hass,
                ha_now(),
                gas_consumption_statistic_id(self._serial_number, self._mprn, is_kwh=False),
                gas_consumption_statistic_name(self._serial_number, self._mprn, is_kwh=False),
                m3_records,
                rate_data,
                UnitOfVolume.CUBIC_METERS,
            )
        )

        self._attributes = dict_to_typed_dict(self._attributes)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = (
                None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            )
            self._attributes = dict_to_typed_dict(state.attributes)
            _LOGGER.debug(f"Restored EDFEnergyPreviousAccumulativeGasConsumptionM3 state: {self._state}")
