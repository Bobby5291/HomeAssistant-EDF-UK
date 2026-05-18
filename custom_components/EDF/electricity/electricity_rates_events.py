# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 [year] — adapted for EDF Energy / Kraken API

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.event import EventEntity, EventExtraStoredData
from homeassistant.helpers.restore_state import RestoreEntity

from .base import EDFEnergyElectricitySensor
from ..utils.attributes import dict_to_typed_dict
from ..const import (
    EVENT_ELECTRICITY_CURRENT_DAY_RATES,
    EVENT_ELECTRICITY_NEXT_DAY_RATES,
    EVENT_ELECTRICITY_PREVIOUS_DAY_RATES,
    EVENT_ELECTRICITY_PREVIOUS_CONSUMPTION_RATES,
)

_LOGGER = logging.getLogger(__name__)


class EDFEnergyElectricityCurrentDayRates(EDFEnergyElectricitySensor, EventEntity, RestoreEntity):
    """Event entity for current day electricity rates."""

    def __init__(self, hass: HomeAssistant, meter, point):
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point, "event")
        self._hass = hass
        self._attr_event_types = [EVENT_ELECTRICITY_CURRENT_DAY_RATES]

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_current_day_rates'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Current Day Rates ({self._serial_number}/{self._mpan})'

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._hass.bus.async_listen(self._attr_event_types[0], self._async_handle_event)

    async def async_get_last_event_data(self):
        data = await super().async_get_last_event_data()
        return EventExtraStoredData.from_dict({
            "last_event_type": data.last_event_type,
            "last_event_attributes": dict_to_typed_dict(data.last_event_attributes),
        })

    @callback
    def _async_handle_event(self, event) -> None:
        if (event.data is not None and
                event.data.get("mpan") == self._mpan and
                event.data.get("serial_number") == self._serial_number):
            self._trigger_event(event.event_type, event.data)
            self.async_write_ha_state()


class EDFEnergyElectricityNextDayRates(EDFEnergyElectricitySensor, EventEntity, RestoreEntity):
    """Event entity for next day electricity rates."""

    def __init__(self, hass: HomeAssistant, meter, point):
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point, "event")
        self._hass = hass
        self._attr_event_types = [EVENT_ELECTRICITY_NEXT_DAY_RATES]

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_next_day_rates'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Next Day Rates ({self._serial_number}/{self._mpan})'

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._hass.bus.async_listen(self._attr_event_types[0], self._async_handle_event)

    async def async_get_last_event_data(self):
        data = await super().async_get_last_event_data()
        return EventExtraStoredData.from_dict({
            "last_event_type": data.last_event_type,
            "last_event_attributes": dict_to_typed_dict(data.last_event_attributes),
        })

    @callback
    def _async_handle_event(self, event) -> None:
        if (event.data is not None and
                event.data.get("mpan") == self._mpan and
                event.data.get("serial_number") == self._serial_number):
            self._trigger_event(event.event_type, event.data)
            self.async_write_ha_state()


class EDFEnergyElectricityPreviousDayRates(EDFEnergyElectricitySensor, EventEntity, RestoreEntity):
    """Event entity for previous day electricity rates."""

    def __init__(self, hass: HomeAssistant, meter, point):
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point, "event")
        self._hass = hass
        self._attr_event_types = [EVENT_ELECTRICITY_PREVIOUS_DAY_RATES]

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_previous_day_rates'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Previous Day Rates ({self._serial_number}/{self._mpan})'

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._hass.bus.async_listen(self._attr_event_types[0], self._async_handle_event)

    async def async_get_last_event_data(self):
        data = await super().async_get_last_event_data()
        return EventExtraStoredData.from_dict({
            "last_event_type": data.last_event_type,
            "last_event_attributes": dict_to_typed_dict(data.last_event_attributes),
        })

    @callback
    def _async_handle_event(self, event) -> None:
        if (event.data is not None and
                event.data.get("mpan") == self._mpan and
                event.data.get("serial_number") == self._serial_number):
            self._trigger_event(event.event_type, event.data)
            self.async_write_ha_state()


class EDFEnergyElectricityPreviousConsumptionRates(EDFEnergyElectricitySensor, EventEntity, RestoreEntity):
    """Event entity for previous consumption electricity rates."""

    def __init__(self, hass: HomeAssistant, meter, point):
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point, "event")
        self._hass = hass
        self._attr_event_types = [EVENT_ELECTRICITY_PREVIOUS_CONSUMPTION_RATES]

    @property
    def unique_id(self):
        return f'edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_previous_consumption_rates'

    @property
    def name(self):
        return f'EDF {self._export_name_addition}Electricity Previous Consumption Rates ({self._serial_number}/{self._mpan})'

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._hass.bus.async_listen(self._attr_event_types[0], self._async_handle_event)

    async def async_get_last_event_data(self):
        data = await super().async_get_last_event_data()
        return EventExtraStoredData.from_dict({
            "last_event_type": data.last_event_type,
            "last_event_attributes": dict_to_typed_dict(data.last_event_attributes),
        })

    @callback
    def _async_handle_event(self, event) -> None:
        if (event.data is not None and
                event.data.get("mpan") == self._mpan and
                event.data.get("serial_number") == self._serial_number):
            self._trigger_event(event.event_type, event.data)
            self.async_write_ha_state()
