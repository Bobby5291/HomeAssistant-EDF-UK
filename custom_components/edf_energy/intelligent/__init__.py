# Bobby5291 2026 — EDF Energy / Kraken API — Intelligent EV base entity

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import DOMAIN


class EDFEnergyIntelligentDevice:
    """Base mixin for EV smart charging entities — provides device_info."""

    def __init__(self, hass: HomeAssistant, account_id: str, device_id: str, make: str | None, model: str | None, device_type: str | None):
        self._hass = hass
        self._account_id = account_id
        self._device_id = device_id
        self._make = make
        self._model = model
        self._device_type = device_type
        self._attributes = {}

    @property
    def device_info(self) -> DeviceInfo:
        manufacturer = self._make or "EDF Energy"
        model = self._model or (self._device_type or "EV Device")
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._account_id}_{self._device_id}_intelligent")},
            name=f"EDF Intelligent ({self._account_id})",
            manufacturer=manufacturer,
            model=model,
        )
