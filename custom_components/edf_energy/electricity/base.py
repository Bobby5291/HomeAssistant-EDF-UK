# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EDFEnergyElectricitySensor:
    """Base class for EDF electricity sensors."""

    def __init__(self, hass: HomeAssistant, meter: dict, point: dict, domain: str = "sensor"):
        self._hass = hass
        self._mpan = point["mpan"]
        self._serial_number = meter["serial_number"]
        self._is_export = meter["is_export"]
        self._is_smart_meter = meter["is_smart_meter"]

        self._export_id_addition = "_export" if self._is_export else ""
        self._export_name_addition = "Export " if self._is_export else ""

        self._attributes = {
            "mpan": self._mpan,
            "serial_number": self._serial_number,
            "is_export": self._is_export,
            "is_smart_meter": self._is_smart_meter,
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._mpan)},
            name=f"EDF {'Export ' if self._is_export else ''}Electricity Meter ({self._mpan})",
            manufacturer=self._attributes.get("manufacturer", "EDF Energy"),
            model=self._attributes.get("model"),
        )
