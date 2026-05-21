# Bobby5291 2026 — EDF Energy / Kraken API — EV smart charging switches

import logging

from homeassistant.components.switch import SwitchEntity
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


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up EDF Energy intelligent switches."""
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
        EDFEnergyIntelligentSmartChargeSwitch(hass, coordinator, account_id, device_info),
        EDFEnergyIntelligentBumpChargeSwitch(hass, coordinator, account_id, device_info),
    ])


class _IntelligentSwitchBase(CoordinatorEntity, EDFEnergyIntelligentDevice, SwitchEntity):

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str, device_info: dict):
        self._device_id = device_info["id"]
        EDFEnergyIntelligentDevice.__init__(
            self, hass, account_id, self._device_id,
            device_info.get("make"), device_info.get("model"), device_info.get("device_type")
        )
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def extra_state_attributes(self):
        return self._attributes


class EDFEnergyIntelligentSmartChargeSwitch(_IntelligentSwitchBase):
    """Switch that enables/disables smart (off-peak) charging."""

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._device_id}_intelligent_smart_charge"

    @property
    def name(self):
        return f"EDF Intelligent Smart Charge ({self._account_id})"

    @property
    def icon(self):
        return "mdi:ev-plug-type2"

    @property
    def is_on(self):
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is None:
            return None
        return not result.is_suspended

    @callback
    def _handle_coordinator_update(self) -> None:
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is not None:
            self._attributes = {
                "current_state": result.current_state,
                "is_suspended": result.is_suspended,
            }
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs):
        client = self.hass.data[DOMAIN][self._account_id][DATA_CLIENT]
        await client.async_set_intelligent_smart_control(self._device_id, suspend=False)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        client = self.hass.data[DOMAIN][self._account_id][DATA_CLIENT]
        await client.async_set_intelligent_smart_control(self._device_id, suspend=True)
        await self.coordinator.async_request_refresh()


class EDFEnergyIntelligentBumpChargeSwitch(_IntelligentSwitchBase):
    """Switch that starts/cancels a bump (immediate) charge."""

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._device_id}_intelligent_bump_charge"

    @property
    def name(self):
        return f"EDF Intelligent Bump Charge ({self._account_id})"

    @property
    def icon(self):
        return "mdi:lightning-bolt"

    @property
    def is_on(self):
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is None:
            return None
        return result.is_bump_charging

    @callback
    def _handle_coordinator_update(self) -> None:
        result: IntelligentCoordinatorResult | None = self.coordinator.data
        if result is not None:
            self._attributes = {
                "current_state": result.current_state,
            }
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs):
        client = self.hass.data[DOMAIN][self._account_id][DATA_CLIENT]
        await client.async_set_intelligent_boost_charge(self._device_id, boost=True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        client = self.hass.data[DOMAIN][self._account_id][DATA_CLIENT]
        await client.async_set_intelligent_boost_charge(self._device_id, boost=False)
        await self.coordinator.async_request_refresh()
