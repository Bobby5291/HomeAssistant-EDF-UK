# Bobby5291 2026 — EDF Energy / Kraken API

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.util.dt import now, as_utc

from .base import EDFEnergyElectricitySensor
from ..utils.attributes import dict_to_typed_dict
from ..coordinators.electricity_rates import ElectricityRatesCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class EDFEnergyElectricityNextDayRatesAvailable(
    CoordinatorEntity, EDFEnergyElectricitySensor, BinarySensorEntity, RestoreEntity
):
    """
    Binary sensor — ON when tomorrow's electricity rates have been published by EDF.
    Useful for triggering automations that plan ahead once prices are known.
    """

    def __init__(self, hass: HomeAssistant, coordinator, meter: dict, point: dict):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = False
        self._attributes.update({
            "next_day_rate_count": None,
            "next_day_min_rate": None,
            "next_day_max_rate": None,
        })

    @property
    def unique_id(self):
        return (
            f'edf_energy_electricity_{self._serial_number}_{self._mpan}'
            f'{self._export_id_addition}_next_day_rates_available'
        )

    @property
    def name(self):
        return (
            f'EDF {self._export_name_addition}Electricity Next Day Rates Available '
            f'({self._serial_number}/{self._mpan})'
        )

    @property
    def icon(self):
        return "mdi:calendar-check"

    @property
    def is_on(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        from ..utils.conversions import pence_to_pounds_pence_accurate

        current = now()
        tomorrow_start = as_utc(
            (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        )

        rates_result: ElectricityRatesCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )

        if rates_result is not None and rates_result.rates:
            next_day_rates = [r for r in rates_result.rates if r["start"] >= tomorrow_start]
            has_next_day = len(next_day_rates) > 0
            self._state = has_next_day
            if has_next_day:
                values = [r["value_inc_vat"] for r in next_day_rates]
                self._attributes.update({
                    "next_day_rate_count": len(next_day_rates),
                    "next_day_min_rate": pence_to_pounds_pence_accurate(min(values)),
                    "next_day_max_rate": pence_to_pounds_pence_accurate(max(values)),
                })
            else:
                self._attributes.update({
                    "next_day_rate_count": 0,
                    "next_day_min_rate": None,
                    "next_day_max_rate": None,
                })
        else:
            self._state = False

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None:
            from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
            self._state = (
                state.state.lower() == "on"
                if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
                else False
            )
            _LOGGER.debug(f'Restored {self.unique_id} state: {self._state}')
