# Bobby5291 2026 — EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass

from ..coordinators.account import AccountCoordinatorResult
from ..coordinators.account_transactions import AccountTransactionsCoordinatorResult
from ..utils.attributes import dict_to_typed_dict
from ..const import DOMAIN
from .balance import EDFEnergyAccountSensor

_LOGGER = logging.getLogger(__name__)


class EDFEnergyDirectDebitAmount(CoordinatorEntity, EDFEnergyAccountSensor, RestoreSensor):
    """Monthly direct debit amount in GBP."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = None

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_direct_debit_amount"

    @property
    def name(self):
        return f"EDF Direct Debit Amount ({self._account_id})"

    @property
    def device_class(self):
        return SensorDeviceClass.MONETARY

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self):
        return "GBP"

    @property
    def icon(self):
        return "mdi:bank-transfer-out"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AccountCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        if result is not None and result.account is not None:
            amount = result.account.get("direct_debit_amount")
            self._state = round(amount / 100, 2) if amount is not None else None
            self._attributes.update({
                "payment_day": result.account.get("direct_debit_payment_day"),
                "status": result.account.get("direct_debit_status"),
            })
        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            _LOGGER.debug(f'Restored EDFEnergyDirectDebitAmount state: {self._state}')


class EDFEnergyLastPayment(CoordinatorEntity, EDFEnergyAccountSensor, RestoreSensor):
    """
    Most recent credit (payment) on the account in GBP.
    State = payment amount. Attributes include posted_date and title.
    """

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = None

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_last_payment"

    @property
    def name(self):
        return f"EDF Last Payment ({self._account_id})"

    @property
    def device_class(self):
        return SensorDeviceClass.MONETARY

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self):
        return "GBP"

    @property
    def icon(self):
        return "mdi:cash-check"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AccountTransactionsCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        if result is not None and result.transactions:
            # Find the most recent credit (payment) transaction
            payments = [t for t in result.transactions if t.get("is_credit") is True]
            if payments:
                latest = payments[0]
                gross = latest.get("gross_amount")
                self._state = round(gross / 100, 2) if gross is not None else None
                self._attributes.update({
                    "posted_date": latest.get("posted_date"),
                    "title": latest.get("title"),
                })
        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
            _LOGGER.debug(f'Restored EDFEnergyLastPayment state: {self._state}')
