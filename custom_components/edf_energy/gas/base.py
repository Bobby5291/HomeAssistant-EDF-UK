# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EDFEnergyGasSensor:
    """Base class for EDF gas sensors."""

    def __init__(self, hass: HomeAssistant, meter: dict, point: dict):
        self._hass = hass
        self._mprn = point["mprn"]
        self._serial_number = meter["serial_number"]
        self._is_smart_meter = meter.get("is_smart_meter", False)
        self._manufacturer = meter.get("manufacturer", "EDF Energy")
        self._model = meter.get("model")

        self._attributes = {
            "mprn": self._mprn,
            "serial_number": self._serial_number,
            "is_smart_meter": self._is_smart_meter,
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._mprn)},
            name=f"EDF Gas Meter ({self._mprn})",
            manufacturer=self._manufacturer,
            model=self._model,
        )
