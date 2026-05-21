# Bobby5291 2026 — EDF Energy / Kraken API — Electricity off-peak binary sensor

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import now as ha_now

from .base import EDFEnergyElectricitySensor
from ..utils.attributes import dict_to_typed_dict
from ..utils.rate_information import get_off_peak_times

_LOGGER = logging.getLogger(__name__)


class EDFEnergyElectricityOffPeak(CoordinatorEntity, EDFEnergyElectricitySensor, BinarySensorEntity, RestoreEntity):
    """Binary sensor — ON when the current rate is at the off-peak (minimum) level.

    Exposes current and next off-peak window times as attributes.
    """

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = False
        self._attributes.update({
            "current_start": None,
            "current_end": None,
            "next_start": None,
            "next_end": None,
        })

    @property
    def unique_id(self):
        return f"edf_energy_electricity_{self._serial_number}_{self._mpan}{self._export_id_addition}_off_peak"

    @property
    def name(self):
        return f"EDF {self._export_name_addition}Electricity Off Peak ({self._serial_number}/{self._mpan})"

    @property
    def icon(self):
        return "mdi:lightning-bolt-outline"

    @property
    def is_on(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        current = ha_now()
        rates = (
            self.coordinator.data.rates
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )

        if rates is not None:
            windows = get_off_peak_times(current, rates)
            self._state = False
            self._attributes.update({
                "current_start": None,
                "current_end": None,
                "next_start": None,
                "next_end": None,
            })

            remaining = list(windows)
            if remaining:
                first = remaining.pop(0)
                if first["start"] <= current < first["end"]:
                    self._state = True
                    self._attributes["current_start"] = first["start"]
                    self._attributes["current_end"] = first["end"]
                    if remaining:
                        self._attributes["next_start"] = remaining[0]["start"]
                        self._attributes["next_end"] = remaining[0]["end"]
                else:
                    self._attributes["next_start"] = first["start"]
                    self._attributes["next_end"] = first["end"]

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._state = state.state.lower() == "on"
            self._attributes = dict_to_typed_dict(state.attributes)
        _LOGGER.debug(f"Restored EDFEnergyElectricityOffPeak state: {self._state}")
