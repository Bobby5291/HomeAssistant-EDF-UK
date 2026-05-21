# Bobby5291 2026 — EDF Energy / Kraken API

import logging
from datetime import datetime

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import RestoreSensor, SensorStateClass

from ..coordinators.account import AccountCoordinatorResult
from ..utils.attributes import dict_to_typed_dict
from ..utils import get_active_tariff, get_tariff_parts
from ..const import DOMAIN
from .balance import EDFEnergyAccountSensor

_LOGGER = logging.getLogger(__name__)


def _classify_tariff(tariff_code: str) -> str:
    """Return a human-readable tariff type label from the tariff code."""
    if not tariff_code:
        return "Unknown"
    parts = get_tariff_parts(tariff_code)
    if parts is None:
        return "Unknown"
    rate = (parts.rate or "").upper()
    if "EV" in rate:
        return "EV"
    if "HH" in rate:
        return "Smart / Half-Hourly"
    if "2R" in rate or "FLAT2R" in rate or "E7" in rate:
        return "Economy 7"
    return "Standard"


class EDFEnergyElectricityTariff(CoordinatorEntity, EDFEnergyAccountSensor, RestoreSensor):
    """
    Sensor showing the current electricity tariff name.
    State = display name (e.g. 'EDF FreePhase Dynamic').
    Attributes include tariff code, product code, valid from/to.
    """

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str, mpan: str):
        CoordinatorEntity.__init__(self, coordinator)
        self._mpan = mpan
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = None
        self._attributes.update({
            "mpan": mpan,
            "tariff_code": None,
            "product_code": None,
            "display_name": None,
            "valid_from": None,
            "valid_to": None,
        })

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._mpan}_electricity_tariff"

    @property
    def name(self):
        return f"EDF Electricity Tariff ({self._mpan})"

    @property
    def icon(self):
        return "mdi:lightning-bolt-circle"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_value(self):
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        from homeassistant.util.dt import now
        result: AccountCoordinatorResult = self.coordinator.data if self.coordinator is not None and self.coordinator.data is not None else None

        if result is not None and result.account is not None:
            current = now()
            electricity_points = result.account.get("electricity_meter_points", []) or []

            for point in electricity_points:
                if point.get("mpan") == self._mpan:
                    active_tariff = get_active_tariff(current, point.get("agreements", []))
                    agreements = point.get("agreements", [])

                    # Find the active agreement to get display_name and dates
                    active_agreement = None
                    for agreement in agreements:
                        if (agreement.get("tariff_code") == (active_tariff.code if active_tariff else None)):
                            active_agreement = agreement
                            break

                    if active_tariff is not None:
                        display_name = active_agreement.get("display_name") if active_agreement else None
                        self._state = display_name or active_tariff.code
                        self._attributes.update({
                            "tariff_code": active_tariff.code,
                            "product_code": active_tariff.product,
                            "display_name": display_name,
                            "valid_from": active_agreement.get("start") if active_agreement else None,
                            "valid_to": active_agreement.get("end") if active_agreement else None,
                        })
                    else:
                        self._state = None
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
            _LOGGER.debug(f'Restored EDFEnergyElectricityTariff state: {self._state}')


class EDFEnergyElectricityTariffType(CoordinatorEntity, EDFEnergyAccountSensor, RestoreSensor):
    """
    Human-readable tariff type for a given electricity MPAN.
    State is one of: Standard, Economy 7, Smart / Half-Hourly, EV, Unknown.
    Derived from the active tariff code — no extra API call.
    """

    def __init__(self, hass: HomeAssistant, coordinator, account_id: str, mpan: str):
        CoordinatorEntity.__init__(self, coordinator)
        self._mpan = mpan
        EDFEnergyAccountSensor.__init__(self, hass, account_id)
        self._state = None
        self._attributes.update({
            "mpan": mpan,
            "tariff_code": None,
        })

    @property
    def unique_id(self):
        return f"edf_energy_{self._account_id}_{self._mpan}_electricity_tariff_type"

    @property
    def name(self):
        return f"EDF Electricity Tariff Type ({self._mpan})"

    @property
    def icon(self):
        return "mdi:tag-text"

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
            for point in result.account.get("electricity_meter_points", []) or []:
                if point.get("mpan") == self._mpan:
                    active_tariff = get_active_tariff(current, point.get("agreements", []))
                    if active_tariff is not None:
                        self._state = _classify_tariff(active_tariff.code)
                        self._attributes["tariff_code"] = active_tariff.code
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
            _LOGGER.debug(f'Restored EDFEnergyElectricityTariffType state: {self._state}')
