# Bobby5291 2026 — EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass
from homeassistant.components.binary_sensor import BinarySensorEntity

from ..coordinators.account import AccountCoordinatorResult
from ..utils.attributes import dict_to_typed_dict
from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EDFEnergyAccountSensor:
    """Base class for EDF account-level sensors."""

    def __init__(self, hass: HomeAssistant, account_id: str):
        self._account_id = account_id
        self._attributes = {"account_id": account_id}

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"account_{account_id}")},
            name=f"EDF Energy Account ({account_id})",
            manufacturer="EDF Energy",
        )

        self.entity_id = generate_entity_id("sensor.{}", self.unique_id, hass=hass)


class EDFEnergyAccountBalance(CoordinatorEntity, EDFEnergyAccountSensor, RestoreSensor):
    """Current account balance in GBP. Positive = in credit, negative = in debt."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = None

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_account_balance"

    @property
    def name(self):
        return f"EDF Account Balance ({self._account_id})"

    @property
    def device_class(self):
        return SensorDeviceClass.MONETARY

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def native_unit_of_measurement(self):
        return "GBP"

    @property
    def icon(self):
        return "mdi:currency-gbp"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AccountCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None

        if result is not None and result.account is not None:
            balance = result.account.get("balance")
            # EDF returns balance in pence
            self._state = round(balance / 100, 2) if balance is not None else None
            self._attributes["last_updated"] = result.last_evaluated

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            _LOGGER.debug(f'Restored EDFEnergyAccountBalance state: {self._state}')


class EDFEnergyProjectedBalance(CoordinatorEntity, EDFEnergyAccountSensor, RestoreSensor):
    """EDF's forecast of your balance at next billing date."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = None

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_projected_balance"

    @property
    def name(self):
        return f"EDF Projected Balance ({self._account_id})"

    @property
    def device_class(self):
        return SensorDeviceClass.MONETARY

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def native_unit_of_measurement(self):
        return "GBP"

    @property
    def icon(self):
        return "mdi:currency-gbp"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AccountCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None

        if result is not None and result.account is not None:
            projected = result.account.get("projected_balance")
            self._state = round(projected / 100, 2) if projected is not None else None

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            _LOGGER.debug(f'Restored EDFEnergyProjectedBalance state: {self._state}')


class EDFEnergyRecommendedBalanceAdjustment(CoordinatorEntity, EDFEnergyAccountSensor, RestoreSensor):
    """EDF's recommended direct debit adjustment amount in GBP."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = None

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_recommended_balance_adjustment"

    @property
    def name(self):
        return f"EDF Recommended DD Adjustment ({self._account_id})"

    @property
    def device_class(self):
        return SensorDeviceClass.MONETARY

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def native_unit_of_measurement(self):
        return "GBP"

    @property
    def icon(self):
        return "mdi:bank-transfer"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AccountCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None

        if result is not None and result.account is not None:
            adjustment = result.account.get("recommended_balance_adjustment")
            self._state = round(adjustment / 100, 2) if adjustment is not None else None
            self._attributes["should_review_payments"] = result.account.get("should_review_payments")

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            _LOGGER.debug(f'Restored EDFEnergyRecommendedBalanceAdjustment state: {self._state}')


class EDFEnergyOverdueBalance(CoordinatorEntity, EDFEnergyAccountSensor, RestoreSensor):
    """Any overdue balance on the account in GBP."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = None

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_overdue_balance"

    @property
    def name(self):
        return f"EDF Overdue Balance ({self._account_id})"

    @property
    def device_class(self):
        return SensorDeviceClass.MONETARY

    @property
    def state_class(self):
        return SensorStateClass.TOTAL

    @property
    def native_unit_of_measurement(self):
        return "GBP"

    @property
    def icon(self):
        return "mdi:alert-circle"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AccountCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None

        if result is not None and result.account is not None:
            overdue = result.account.get("overdue_balance")
            self._state = round(overdue / 100, 2) if overdue is not None else None

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()

        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            _LOGGER.debug(f'Restored EDFEnergyOverdueBalance state: {self._state}')


class EDFEnergyAccountIsOverdue(CoordinatorEntity, EDFEnergyAccountSensor, BinarySensorEntity, RestoreEntity):
    """Binary sensor — True if there is an overdue balance on the account."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = False
        self.entity_id = generate_entity_id("binary_sensor.{}", self.unique_id, hass=hass)

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_account_is_overdue"

    @property
    def name(self):
        return f"EDF Account Is Overdue ({self._account_id})"

    @property
    def icon(self):
        return "mdi:alert-circle-outline"

    @property
    def is_on(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AccountCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None

        if result is not None and result.account is not None:
            overdue = result.account.get("overdue_balance")
            self._state = overdue is not None and overdue > 0
            self._attributes["overdue_balance_gbp"] = round(overdue / 100, 2) if overdue is not None else None

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()

        if state is not None and self._state is None:
            self._state = state.state.lower() == "on" if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN) else False
            _LOGGER.debug(f'Restored EDFEnergyAccountIsOverdue state: {self._state}')


class EDFEnergyDirectDebitNeedsReview(CoordinatorEntity, EDFEnergyAccountSensor, BinarySensorEntity, RestoreEntity):
    """Binary sensor — True if EDF recommends reviewing your direct debit amount."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = False
        self.entity_id = generate_entity_id("binary_sensor.{}", self.unique_id, hass=hass)

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_direct_debit_needs_review"

    @property
    def name(self):
        return f"EDF Direct Debit Needs Review ({self._account_id})"

    @property
    def icon(self):
        return "mdi:bank-alert"

    @property
    def is_on(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AccountCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None

        if result is not None and result.account is not None:
            self._state = result.account.get("should_review_payments") == True
            adjustment = result.account.get("recommended_balance_adjustment")
            self._attributes["recommended_adjustment_gbp"] = round(adjustment / 100, 2) if adjustment is not None else None

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()

        if state is not None and self._state is None:
            self._state = state.state.lower() == "on" if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN) else False
            _LOGGER.debug(f'Restored EDFEnergyDirectDebitNeedsReview state: {self._state}')
