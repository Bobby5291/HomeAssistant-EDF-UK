# Bobby5291 2026 — EDF Energy / Kraken API — Electricity export total sensor

import logging

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import now as ha_now

from .base import EDFEnergyElectricitySensor
from ..utils.attributes import dict_to_typed_dict
from ..coordinators.current_consumption import CurrentConsumptionCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class EDFEnergyCurrentTotalElectricityExport(CoordinatorEntity, EDFEnergyElectricitySensor, RestoreSensor):
    """Sensor showing the cumulative electricity export total for the current day (from smart meter telemetry)."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None
        self._last_reset = None

    @property
    def unique_id(self):
        return f"edf_energy_electricity_{self._serial_number}_{self._mpan}_current_total_export"

    @property
    def name(self):
        return f"EDF Current Total Electricity Export ({self._serial_number}/{self._mpan})"

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
        return "mdi:transmission-tower-export"

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        result: CurrentConsumptionCoordinatorResult | None = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        data = result.data if result is not None else None

        if data and len(data) > 0:
            last = data[-1]
            export = last.get("total_export")
            if export is not None and export != 0:
                self._state = export
                self._last_reset = ha_now()

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
        _LOGGER.debug(f"Restored EDFEnergyCurrentTotalElectricityExport state: {self._state}")
