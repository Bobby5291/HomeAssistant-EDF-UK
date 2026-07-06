# Bobby5291 2026 — EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass

from ..utils.attributes import dict_to_typed_dict
from ..coordinators.annual_gas_consumption import AnnualGasConsumptionCoordinatorResult
from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EDFEnergyGasAnnualQuantity(CoordinatorEntity, RestoreSensor):
    """
    Annual Quantity (AQ) for a gas meter point in kWh/year.
    This is the industry-standard annual consumption figure used for billing estimates.
    """

    def __init__(self, hass: HomeAssistant, coordinator, mprn: str):
        CoordinatorEntity.__init__(self, coordinator)
        self._mprn = mprn
        self._state = None
        self._attributes = {"mprn": mprn}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mprn)},
            name=f"EDF Gas Meter ({mprn})",
            manufacturer="EDF Energy",
        )
        self.entity_id = generate_entity_id("sensor.{}", self.unique_id, hass=hass)

    @property
    def unique_id(self):
        return f"edf_energy_{self._mprn}_gas_annual_quantity"

    @property
    def name(self):
        return f"EDF Gas Annual Quantity ({self._mprn})"

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def device_class(self):
        return SensorDeviceClass.ENERGY

    @property
    def native_unit_of_measurement(self):
        return "kWh"

    @property
    def icon(self):
        return "mdi:fire"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AnnualGasConsumptionCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        if result is not None:
            self._state = result.aq
            self._attributes.update({
                "supplier_name": result.supplier_name,
                "supplier_effective_from": result.supplier_effective_from,
                "aq_effective_from": result.aq_effective_from,
                "last_updated": result.last_evaluated,
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
            _LOGGER.debug(f'Restored EDFEnergyGasAnnualQuantity state: {self._state}')
