# Bobby5291 2026 — EDF Energy / Kraken API

import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorEntity

from ..coordinators.account import AccountCoordinatorResult
from ..utils.attributes import dict_to_typed_dict
from ..utils import get_active_tariff
from ..const import DOMAIN
from .balance import EDFEnergyAccountSensor

_LOGGER = logging.getLogger(__name__)


class EDFEnergyCanRenewTariff(CoordinatorEntity, EDFEnergyAccountSensor, BinarySensorEntity, RestoreEntity):
    """Binary sensor — True if EDF indicates your tariff is eligible for renewal."""

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str):
        CoordinatorEntity.__init__(self, coordinator)
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = False
        self.entity_id = generate_entity_id("binary_sensor.{}", self.unique_id, hass=hass)

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_can_renew_tariff"

    @property
    def name(self):
        return f"EDF Can Renew Tariff ({self._account_id})"

    @property
    def icon(self):
        return "mdi:refresh-circle"

    @property
    def is_on(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        result: AccountCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        if result is not None and result.account is not None:
            self._state = result.account.get("can_renew_tariff") == True
        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._state = state.state.lower() == "on"
            _LOGGER.debug(f'Restored EDFEnergyCanRenewTariff state: {self._state}')


class EDFEnergyElectricityContractEnd(CoordinatorEntity, EDFEnergyAccountSensor, RestoreSensor):
    """
    Sensor showing the electricity contract end date for a given MPAN.
    State is the ISO-8601 end date string (or None for rolling contracts).
    """

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str, mpan: str):
        CoordinatorEntity.__init__(self, coordinator)
        self._mpan = mpan
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = None
        self._attributes.update({
            "mpan": mpan,
            "tariff_code": None,
            "contract_start": None,
        })

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._mpan}_electricity_contract_end"

    @property
    def name(self):
        return f"EDF Electricity Contract End ({self._mpan})"

    @property
    def device_class(self):
        return SensorDeviceClass.DATE

    @property
    def icon(self):
        return "mdi:calendar-end"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        from homeassistant.util.dt import now
        from homeassistant.util.dt import parse_datetime as ha_parse_dt

        result: AccountCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        if result is not None and result.account is not None:
            current = now()
            for point in result.account.get("electricity_meter_points", []) or []:
                if point.get("mpan") == self._mpan:
                    active_tariff = get_active_tariff(current, point.get("agreements", []))
                    for agreement in point.get("agreements", []):
                        if (active_tariff is not None and
                                agreement.get("tariff_code") == active_tariff.code):
                            end_raw = agreement.get("end")
                            if end_raw is not None:
                                try:
                                    from homeassistant.util.dt import parse_datetime as ha_pd
                                    dt = ha_pd(end_raw)
                                    self._state = dt.date() if dt else end_raw
                                except Exception:
                                    self._state = end_raw
                            else:
                                self._state = None
                            self._attributes.update({
                                "tariff_code": active_tariff.code if active_tariff else None,
                                "contract_start": agreement.get("start"),
                            })
                            break
                    break

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
            _LOGGER.debug(f'Restored EDFEnergyElectricityContractEnd state: {self._state}')


class EDFEnergyGasContractEnd(CoordinatorEntity, EDFEnergyAccountSensor, RestoreSensor):
    """
    Sensor showing the gas contract end date for a given MPRN.
    State is the ISO-8601 end date string (or None for rolling contracts).
    """

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str, mprn: str):
        CoordinatorEntity.__init__(self, coordinator)
        self._mprn = mprn
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = None
        self._attributes.update({
            "mprn": mprn,
            "tariff_code": None,
            "contract_start": None,
        })

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._mprn}_gas_contract_end"

    @property
    def name(self):
        return f"EDF Gas Contract End ({self._mprn})"

    @property
    def device_class(self):
        return SensorDeviceClass.DATE

    @property
    def icon(self):
        return "mdi:calendar-end"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        from homeassistant.util.dt import now

        result: AccountCoordinatorResult = (
            self.coordinator.data
            if self.coordinator is not None and self.coordinator.data is not None
            else None
        )
        if result is not None and result.account is not None:
            current = now()
            for point in result.account.get("gas_meter_points", []) or []:
                if point.get("mprn") == self._mprn:
                    active_tariff = get_active_tariff(current, point.get("agreements", []))
                    for agreement in point.get("agreements", []):
                        if (active_tariff is not None and
                                agreement.get("tariff_code") == active_tariff.code):
                            end_raw = agreement.get("end")
                            if end_raw is not None:
                                try:
                                    from homeassistant.util.dt import parse_datetime as ha_pd
                                    dt = ha_pd(end_raw)
                                    self._state = dt.date() if dt else end_raw
                                except Exception:
                                    self._state = end_raw
                            else:
                                self._state = None
                            self._attributes.update({
                                "tariff_code": active_tariff.code if active_tariff else None,
                                "contract_start": agreement.get("start"),
                            })
                            break
                    break

        self._attributes = dict_to_typed_dict(self._attributes)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if state is not None and last_sensor_state is not None and self._state is None:
            self._state = None if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) else last_sensor_state.native_value
            self._attributes = dict_to_typed_dict(state.attributes)
            _LOGGER.debug(f'Restored EDFEnergyGasContractEnd state: {self._state}')
