# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging

from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .electricity.rates_events import (
    EDFEnergyElectricityCurrentDayRates,
    EDFEnergyElectricityNextDayRates,
    EDFEnergyElectricityPreviousDayRates,
    EDFEnergyElectricityPreviousConsumptionRates,
)

from .utils import get_active_tariff
from .const import (
    CONFIG_ACCOUNT_ID,
    DATA_ACCOUNT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up EDF Energy event entities from a config entry."""
    config = dict(entry.data)
    account_id = config[CONFIG_ACCOUNT_ID]

    account_result = hass.data[DOMAIN][account_id][DATA_ACCOUNT]
    account_info = account_result.account if account_result is not None else None

    if account_info is None:
        _LOGGER.error(f"No account info available for {account_id} — event entities will not be created")
        return

    now = utcnow()
    entities = []

    for point in account_info.get("electricity_meter_points", []) or []:
        active_tariff = get_active_tariff(now, point["agreements"])

        if active_tariff is None:
            continue

        for meter in point["meters"]:
            entities.append(EDFEnergyElectricityCurrentDayRates(hass, meter, point))
            entities.append(EDFEnergyElectricityNextDayRates(hass, meter, point))
            entities.append(EDFEnergyElectricityPreviousDayRates(hass, meter, point))
            entities.append(EDFEnergyElectricityPreviousConsumptionRates(hass, meter, point))

    async_add_entities(entities)
