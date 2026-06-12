# Bobby5291 2026 — EDF Energy Free Phase Dynamic tariff — colour-coded rate sensors

import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import now as ha_now, as_local

from .base import EDFEnergyElectricitySensor
from ..utils.attributes import dict_to_typed_dict
from ..utils.conversions import pence_to_pounds_pence
from ..coordinators.electricity_rates import ElectricityRatesCoordinatorResult

_LOGGER = logging.getLogger(__name__)

COLOUR_GREEN = "green"
COLOUR_AMBER = "amber"
COLOUR_RED = "red"
COLOUR_UNKNOWN = "unknown"


def _rates_for_date(rates: list, target_date) -> list:
    return [r for r in rates if as_local(r["start"]).date() == target_date]


def _classify_by_colour(day_rates: list) -> dict[str, list]:
    """
    Split day's half-hour slots into green / amber / red tiers by price tercile.
    Lowest third = green, middle third = amber, top third = red.
    """
    result = {COLOUR_GREEN: [], COLOUR_AMBER: [], COLOUR_RED: []}
    if not day_rates:
        return result

    sorted_vals = sorted(day_rates, key=lambda r: r["value_inc_vat"])
    n = len(sorted_vals)
    third = max(n // 3, 1)

    colour_map: dict[tuple, str] = {}
    for i, rate in enumerate(sorted_vals):
        if i < third:
            colour = COLOUR_GREEN
        elif i < 2 * third:
            colour = COLOUR_AMBER
        else:
            colour = COLOUR_RED
        colour_map[(rate["start"], rate["end"])] = colour

    for rate in day_rates:
        colour = colour_map.get((rate["start"], rate["end"]), COLOUR_AMBER)
        result[colour].append(rate)

    return result


def _colour_for_now(rates: list, now) -> tuple[str, dict | None]:
    """Return (colour, slot) for the current moment."""
    today = as_local(now).date()
    classified = _classify_by_colour(_rates_for_date(rates, today))
    for colour, slots in classified.items():
        for slot in slots:
            if slot["start"] <= now < slot["end"]:
                return colour, slot
    return COLOUR_UNKNOWN, None


def _average_pence(slots: list) -> float | None:
    if not slots:
        return None
    return round(sum(s["value_inc_vat"] for s in slots) / len(slots), 4)


def _window_attrs(slots: list) -> list:
    return [
        {
            "start": s["start"],
            "end": s["end"],
            "rate_pence": round(s["value_inc_vat"], 4),
            "rate_pounds": pence_to_pounds_pence(s["value_inc_vat"]),
        }
        for s in sorted(slots, key=lambda s: s["start"])
    ]


# ---------------------------------------------------------------------------
# Current period sensor
# ---------------------------------------------------------------------------

class EDFEnergyDynamicCurrentPeriod(CoordinatorEntity, EDFEnergyElectricitySensor):
    """Shows whether the current half-hour is green / amber / red."""

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._colour = COLOUR_UNKNOWN

    @property
    def unique_id(self):
        return f"edf_energy_electricity_{self._serial_number}_{self._mpan}_dynamic_current_period"

    @property
    def name(self):
        return f"EDF Dynamic Current Period ({self._serial_number}/{self._mpan})"

    @property
    def icon(self):
        icons = {COLOUR_GREEN: "mdi:circle", COLOUR_AMBER: "mdi:circle", COLOUR_RED: "mdi:circle"}
        return icons.get(self._colour, "mdi:help-circle")

    @property
    def native_value(self):
        return self._colour

    @property
    def extra_state_attributes(self):
        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        result: ElectricityRatesCoordinatorResult | None = self.coordinator.data
        rates = result.rates if result is not None else []
        now = ha_now()
        colour, slot = _colour_for_now(rates, now)
        self._colour = colour
        self._attributes = dict_to_typed_dict({
            "colour": colour,
            "slot_start": slot["start"] if slot else None,
            "slot_end": slot["end"] if slot else None,
            "rate_pence": round(slot["value_inc_vat"], 4) if slot else None,
            "rate_pounds": pence_to_pounds_pence(slot["value_inc_vat"]) if slot else None,
            "mpan": self._mpan,
            "serial_number": self._serial_number,
        })
        super()._handle_coordinator_update()


# ---------------------------------------------------------------------------
# Base for today/tomorrow colour-tier average sensors
# ---------------------------------------------------------------------------

class _EDFEnergyDynamicColourRate(CoordinatorEntity, EDFEnergyElectricitySensor):
    """Base class for a green/amber/red average rate sensor for a specific day."""

    _colour: str = COLOUR_GREEN
    _day_offset: int = 0  # 0 = today, 1 = tomorrow

    def __init__(self, hass: HomeAssistant, coordinator, meter, point):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyElectricitySensor.__init__(self, hass, meter, point)
        self._state = None

    @property
    def device_class(self):
        return None  # price in pence, not a HA energy device-class

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self):
        return "p/kWh"

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        result: ElectricityRatesCoordinatorResult | None = self.coordinator.data
        rates = result.rates if result is not None else []
        now = ha_now()
        target_date = (as_local(now) + timedelta(days=self._day_offset)).date()
        day_rates = _rates_for_date(rates, target_date)
        classified = _classify_by_colour(day_rates)
        slots = classified.get(self._colour, [])
        self._state = _average_pence(slots)
        self._attributes = dict_to_typed_dict({
            "colour": self._colour,
            "date": str(target_date),
            "slot_count": len(slots),
            "windows": _window_attrs(slots),
            "mpan": self._mpan,
            "serial_number": self._serial_number,
        })
        super()._handle_coordinator_update()


# ---------------------------------------------------------------------------
# Today sensors
# ---------------------------------------------------------------------------

class EDFEnergyDynamicTodayGreenRate(_EDFEnergyDynamicColourRate):
    _colour = COLOUR_GREEN
    _day_offset = 0

    @property
    def unique_id(self):
        return f"edf_energy_electricity_{self._serial_number}_{self._mpan}_dynamic_today_green_rate"

    @property
    def name(self):
        return f"EDF Dynamic Today Green Rate ({self._serial_number}/{self._mpan})"

    @property
    def icon(self):
        return "mdi:circle-slice-8"


class EDFEnergyDynamicTodayAmberRate(_EDFEnergyDynamicColourRate):
    _colour = COLOUR_AMBER
    _day_offset = 0

    @property
    def unique_id(self):
        return f"edf_energy_electricity_{self._serial_number}_{self._mpan}_dynamic_today_amber_rate"

    @property
    def name(self):
        return f"EDF Dynamic Today Amber Rate ({self._serial_number}/{self._mpan})"

    @property
    def icon(self):
        return "mdi:circle-slice-4"


class EDFEnergyDynamicTodayRedRate(_EDFEnergyDynamicColourRate):
    _colour = COLOUR_RED
    _day_offset = 0

    @property
    def unique_id(self):
        return f"edf_energy_electricity_{self._serial_number}_{self._mpan}_dynamic_today_red_rate"

    @property
    def name(self):
        return f"EDF Dynamic Today Red Rate ({self._serial_number}/{self._mpan})"

    @property
    def icon(self):
        return "mdi:circle-outline"


# ---------------------------------------------------------------------------
# Tomorrow sensors
# ---------------------------------------------------------------------------

class EDFEnergyDynamicTomorrowGreenRate(_EDFEnergyDynamicColourRate):
    _colour = COLOUR_GREEN
    _day_offset = 1

    @property
    def unique_id(self):
        return f"edf_energy_electricity_{self._serial_number}_{self._mpan}_dynamic_tomorrow_green_rate"

    @property
    def name(self):
        return f"EDF Dynamic Tomorrow Green Rate ({self._serial_number}/{self._mpan})"

    @property
    def icon(self):
        return "mdi:circle-slice-8"


class EDFEnergyDynamicTomorrowAmberRate(_EDFEnergyDynamicColourRate):
    _colour = COLOUR_AMBER
    _day_offset = 1

    @property
    def unique_id(self):
        return f"edf_energy_electricity_{self._serial_number}_{self._mpan}_dynamic_tomorrow_amber_rate"

    @property
    def name(self):
        return f"EDF Dynamic Tomorrow Amber Rate ({self._serial_number}/{self._mpan})"

    @property
    def icon(self):
        return "mdi:circle-slice-4"


class EDFEnergyDynamicTomorrowRedRate(_EDFEnergyDynamicColourRate):
    _colour = COLOUR_RED
    _day_offset = 1

    @property
    def unique_id(self):
        return f"edf_energy_electricity_{self._serial_number}_{self._mpan}_dynamic_tomorrow_red_rate"

    @property
    def name(self):
        return f"EDF Dynamic Tomorrow Red Rate ({self._serial_number}/{self._mpan})"

    @property
    def icon(self):
        return "mdi:circle-outline"
