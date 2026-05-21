# Bobby5291 2026 — EDF Energy / Kraken API

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.util.dt import now

from .base import EDFEnergyElectricitySensor
from ..utils.attributes import dict_to_typed_dict
from ..utils.target_rates import get_target_rate_info
from ..coordinators.electricity_rates import ElectricityRatesCoordinatorResult

_LOGGER = logging.getLogger(__name__)


class EDFEnergyElectricityTargetRateBinarySensor(
    CoordinatorEntity, EDFEnergyElectricitySensor, BinarySensorEntity, RestoreEntity
):
    """
    Binary sensor that is ON when the current time falls within the cheapest
    contiguous window of `_duration_minutes` in the next 24 hours.

    Great for automating EV charging, dishwashers, washing machines etc.
    Attributes expose the exact window start/end and average rate so users
    can build time-condition automations without hard-coding times.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
        meter: dict,
        point: dict,
        duration_minutes: int,
    ):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._duration_minutes = duration_minutes
        self._state = False
        self._attributes.update({
            "duration_minutes": duration_minutes,
            "target_start": None,
            "target_end": None,
            "average_rate": None,
            "min_rate": None,
            "max_rate": None,
        })

    @property
    def unique_id(self):
        mins = self._duration_minutes
        return (
            f'edf_energy_electricity_{self._serial_number}_{self._mpan}'
            f'{self._export_id_addition}_cheapest_{mins}min'
        )

    @property
    def name(self):
        h = self._duration_minutes // 60
        m = self._duration_minutes % 60
        label = f"{h}h" if m == 0 else f"{h}h{m}m" if h else f"{m}m"
        return (
            f'EDF {self._export_name_addition}Electricity Cheapest {label} '
            f'({self._serial_number}/{self._mpan})'
        )

    @property
    def device_class(self):
        return BinarySensorDeviceClass.RUNNING

    @property
    def icon(self):
        return "mdi:cash-clock"

    @property
    def is_on(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        current = now()
        rates_result: ElectricityRatesCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )

        if rates_result is not None and rates_result.rates:
            info = get_target_rate_info(rates_result.rates, self._duration_minutes, current)
            if info is not None:
                self._state = info["is_active"]
                self._attributes.update({
                    "target_start": info["target_start"],
                    "target_end": info["target_end"],
                    "average_rate": info["average_rate"],
                    "min_rate": info["min_rate"],
                    "max_rate": info["max_rate"],
                    "rates_in_period": info["rates_in_period"],
                })
            else:
                self._state = False
                self._attributes.update({
                    "target_start": None,
                    "target_end": None,
                    "average_rate": None,
                    "min_rate": None,
                    "max_rate": None,
                })
        else:
            self._state = False

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and self._state is False:
            from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
            self._state = (
                state.state.lower() == "on"
                if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
                else False
            )
            _LOGGER.debug(f'Restored {self.unique_id} state: {self._state}')
