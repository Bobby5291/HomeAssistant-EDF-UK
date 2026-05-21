# Bobby5291 2026 — EDF Energy / Kraken API — EV charge target number entity

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .intelligent import EDFEnergyIntelligentDevice
from .coordinators.intelligent import IntelligentCoordinatorResult
from .const import (
    CONFIG_ACCOUNT_ID,
    DATA_CLIENT,
    DATA_INTELLIGENT_COORDINATOR_KEY,
    DATA_INTELLIGENT_DEVICE_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIME = "07:00"


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up EDF Energy intelligent number entities."""
    config = dict(entry.data)
    account_id = config[CONFIG_ACCOUNT_ID]

    device_info = hass.data[DOMAIN][account_id].get(DATA_INTELLIGENT_DEVICE_KEY.format(account_id))
    if device_info is None:
        return

    device_id = device_info["id"]
    coordinator_key = DATA_INTELLIGENT_COORDINATOR_KEY.format(device_id)
    coordinator = hass.data[DOMAIN][account_id].get(coordinator_key)
    if coordinator is None:
        return

    async_add_entities([
        EDFEnergyIntelligentChargeTargetNumber(hass, coordinator, account_id, device_info),
    ])


class EDFEnergyIntelligentChargeTargetNumber(CoordinatorEntity, EDFEnergyIntelligentDevice, NumberEntity):
    """Number entity for setting the EV charge target percentage."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str, device_info: dict):
        self._device_id = device_info["id"]
        EDFEnergyIntelligentDevice.__init__(
            self, hass, account_id, self._device_id,
            device_info.get("make"), device_info.get("model"), device_info.get("device_type")
        )
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._device_id}_intelligent_charge_target"

    @property
    def name(self):
        return f"EDF Intelligent Charge Target ({self._account_id})"

    @property
    def icon(self):
        return "mdi:battery-charging-80"

    @property
    def native_min_value(self):
        return 10

    @property
    def native_max_value(self):
        return 100

    @property
    def native_step(self):
        return 5

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def mode(self):
        return NumberMode.SLIDER

    @property
    def native_value(self):
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is not None and result.target_percentage is not None:
            return result.target_percentage
        return 80

    @callback
    def _handle_coordinator_update(self) -> None:
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        client = self.hass.data[DOMAIN][self._account_id][DATA_CLIENT]
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        target_time = (result.target_time if result and result.target_time else DEFAULT_TIME)
        await client.async_set_intelligent_preferences(self._device_id, int(value), target_time)
        await self.coordinator.async_request_refresh()
