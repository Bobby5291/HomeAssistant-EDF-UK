# Bobby5291 2026 — EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass

from ..utils.attributes import dict_to_typed_dict
from ..coordinators.annual_electricity_consumption import AnnualElectricityConsumptionCoordinatorResult
from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EDFEnergyElectricityAnnualConsumptionBase(CoordinatorEntity, RestoreSensor):
    """Base for annual electricity consumption (EAC) sensors."""

    def __init__(self, hass: HomeAssistant, coordinator, mpan: str):
        CoordinatorEntity.__init__(self, coordinator)
        self._mpan = mpan
        self._state = None
        self._attributes = {"mpan": mpan}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mpan)},
            name=f"EDF Electricity Meter ({mpan})",
            manufacturer="EDF Energy",
        )

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def device_class(self):
        return SensorDeviceClass.ENERGY

    @property
    def native_unit_of_measurement(self):
        return "kWh"

    @property
    def icon(self):
        return "mdi:lightning-bolt"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            _LOGGER.debug(f'Restored {self.unique_id} state: {self._state}')


class EDFEnergyElectricityEACStandard(EDFEnergyElectricityAnnualConsumptionBase):
    """Estimated Annual Consumption — standard (single-rate) in kWh/year."""

    def __init__(self, hass: HomeAssistant, coordinator, mpan: str):
        super().__init__(hass, coordinator, mpan)
        self.entity_id = generate_entity_id("sensor.{}", self.unique_id, hass=hass)

    @property
    def unique_id(self):
        return f"edf_energy_{self._mpan}_eac_standard"

    @property
    def name(self):
        return f"EDF Electricity EAC Standard ({self._mpan})"

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AnnualElectricityConsumptionCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        if result is not None:
            self._state = result.eac_standard
            self._attributes["last_updated"] = result.last_evaluated
        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()


class EDFEnergyElectricityEACDay(EDFEnergyElectricityAnnualConsumptionBase):
    """Estimated Annual Consumption — day (peak) rate in kWh/year. Economy 7 accounts only."""

    def __init__(self, hass: HomeAssistant, coordinator, mpan: str):
        super().__init__(hass, coordinator, mpan)
        self.entity_id = generate_entity_id("sensor.{}", self.unique_id, hass=hass)

    @property
    def unique_id(self):
        return f"edf_energy_{self._mpan}_eac_day"

    @property
    def name(self):
        return f"EDF Electricity EAC Day ({self._mpan})"

    @property
    def icon(self):
        return "mdi:weather-sunny"

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AnnualElectricityConsumptionCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        if result is not None:
            self._state = result.eac_day
            self._attributes["last_updated"] = result.last_evaluated
        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()


class EDFEnergyElectricityEACNight(EDFEnergyElectricityAnnualConsumptionBase):
    """Estimated Annual Consumption — night (off-peak) rate in kWh/year. Economy 7 accounts only."""

    def __init__(self, hass: HomeAssistant, coordinator, mpan: str):
        super().__init__(hass, coordinator, mpan)
        self.entity_id = generate_entity_id("sensor.{}", self.unique_id, hass=hass)

    @property
    def unique_id(self):
        return f"edf_energy_{self._mpan}_eac_night"

    @property
    def name(self):
        return f"EDF Electricity EAC Night ({self._mpan})"

    @property
    def icon(self):
        return "mdi:weather-night"

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AnnualElectricityConsumptionCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        if result is not None:
            self._state = result.eac_night
            self._attributes["last_updated"] = result.last_evaluated
        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()
