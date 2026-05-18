# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging

from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .electricity.current_rate import EDFEnergyElectricityCurrentRate
from .electricity.next_rate import EDFEnergyElectricityNextRate
from .electricity.previous_rate import EDFEnergyElectricityPreviousRate
from .electricity.standing_charge import EDFEnergyElectricityCurrentStandingCharge
from .electricity.current_sensors import (
    EDFEnergyCurrentElectricityConsumption,
    EDFEnergyCurrentElectricityDemand,
    EDFEnergyCurrentTotalElectricityConsumption,
    EDFEnergyCurrentAccumulativeElectricityConsumption,
    EDFEnergyCurrentAccumulativeElectricityCost,
)
from .electricity.previous_consumption import (
    EDFEnergyPreviousAccumulativeElectricityConsumption,
    EDFEnergyPreviousAccumulativeElectricityCost,
)
from .account.balance import (
    EDFEnergyAccountBalance,
    EDFEnergyProjectedBalance,
    EDFEnergyOverdueBalance,
    EDFEnergyRecommendedBalanceAdjustment,
)
from .account.tariff import EDFEnergyElectricityTariff

from .utils import get_active_tariff
from .const import (
    CONFIG_ACCOUNT_ID,
    CONFIG_MAIN_SUPPORTS_LIVE_CONSUMPTION,
    CONFIG_MAIN_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
    CONFIG_DEFAULT_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
    DATA_ACCOUNT,
    DATA_ACCOUNT_COORDINATOR,
    DATA_CLIENT,
    DATA_CURRENT_CONSUMPTION_KEY,
    DATA_ELECTRICITY_RATES_COORDINATOR_KEY,
    DATA_ELECTRICITY_STANDING_CHARGE_COORDINATOR_KEY,
    DATA_PREVIOUS_CONSUMPTION_COORDINATOR_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up EDF Energy sensors from a config entry."""
    config = dict(entry.data)
    account_id = config[CONFIG_ACCOUNT_ID]

    account_result = hass.data[DOMAIN][account_id][DATA_ACCOUNT]
    account_info = account_result.account if account_result is not None else None
    account_coordinator = hass.data[DOMAIN][account_id][DATA_ACCOUNT_COORDINATOR]

    if account_info is None:
        _LOGGER.error(f"No account info available for {account_id} — sensors will not be created")
        return

    now = utcnow()
    entities = []

    # -------------------------------------------------------------------------
    # Account-level sensors (balance, tariff)
    # -------------------------------------------------------------------------
    entities.append(EDFEnergyAccountBalance(hass, account_coordinator, account_id))
    entities.append(EDFEnergyProjectedBalance(hass, account_coordinator, account_id))
    entities.append(EDFEnergyOverdueBalance(hass, account_coordinator, account_id))
    entities.append(EDFEnergyRecommendedBalanceAdjustment(hass, account_coordinator, account_id))

    # -------------------------------------------------------------------------
    # Electricity meter sensors — one set per active meter
    # -------------------------------------------------------------------------
    supports_live = config.get(CONFIG_MAIN_SUPPORTS_LIVE_CONSUMPTION, False)
    live_refresh_rate = config.get(
        CONFIG_MAIN_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
        CONFIG_DEFAULT_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
    )

    for point in account_info.get("electricity_meter_points", []) or []:
        mpan = point["mpan"]
        active_tariff = get_active_tariff(now, point["agreements"])

        if active_tariff is None:
            _LOGGER.warning(f"Skipping electricity sensors for {mpan} — no active tariff found. Check HA logs for tariff parsing details.")
            continue

        # Tariff name sensor
        entities.append(EDFEnergyElectricityTariff(hass, account_coordinator, account_id, mpan))

        for meter in point["meters"]:
            serial_number = meter["serial_number"]
            device_id = meter.get("device_id")

            rates_coordinator_key = DATA_ELECTRICITY_RATES_COORDINATOR_KEY.format(mpan, serial_number)
            standing_charge_coordinator_key = DATA_ELECTRICITY_STANDING_CHARGE_COORDINATOR_KEY.format(mpan, serial_number)
            previous_consumption_coordinator_key = DATA_PREVIOUS_CONSUMPTION_COORDINATOR_KEY.format(mpan, serial_number)

            rates_coordinator = hass.data[DOMAIN][account_id].get(rates_coordinator_key)
            standing_charge_coordinator = hass.data[DOMAIN][account_id].get(standing_charge_coordinator_key)
            previous_consumption_coordinator = hass.data[DOMAIN][account_id].get(previous_consumption_coordinator_key)

            if rates_coordinator is None:
                _LOGGER.warning(f"Rates coordinator not found for {mpan}/{serial_number} — skipping rate sensors")
                continue

            # Rate sensors
            entities.append(EDFEnergyElectricityCurrentRate(hass, rates_coordinator, meter, point))
            entities.append(EDFEnergyElectricityNextRate(hass, rates_coordinator, meter, point))
            entities.append(EDFEnergyElectricityPreviousRate(hass, rates_coordinator, meter, point))

            # Standing charge
            if standing_charge_coordinator is not None:
                entities.append(EDFEnergyElectricityCurrentStandingCharge(hass, standing_charge_coordinator, meter, point))

            # Previous day consumption + cost
            if previous_consumption_coordinator is not None:
                entities.append(EDFEnergyPreviousAccumulativeElectricityConsumption(hass, previous_consumption_coordinator, meter, point))
                entities.append(EDFEnergyPreviousAccumulativeElectricityCost(hass, previous_consumption_coordinator, meter, point))

            # Live smart meter sensors — only if user has SMETS2 and opted in
            if supports_live and device_id is not None:
                consumption_coordinator_key = DATA_CURRENT_CONSUMPTION_KEY.format(device_id)
                consumption_coordinator = hass.data[DOMAIN][account_id].get(consumption_coordinator_key)

                if consumption_coordinator is not None:
                    entities.append(EDFEnergyCurrentElectricityConsumption(hass, consumption_coordinator, meter, point))
                    entities.append(EDFEnergyCurrentElectricityDemand(hass, consumption_coordinator, meter, point))
                    entities.append(EDFEnergyCurrentTotalElectricityConsumption(hass, consumption_coordinator, meter, point))

                    if rates_coordinator is not None and standing_charge_coordinator is not None:
                        entities.append(EDFEnergyCurrentAccumulativeElectricityConsumption(
                            hass, consumption_coordinator, rates_coordinator, standing_charge_coordinator, meter, point
                        ))
                        entities.append(EDFEnergyCurrentAccumulativeElectricityCost(
                            hass, consumption_coordinator, rates_coordinator, standing_charge_coordinator, meter, point
                        ))

    async_add_entities(entities)
