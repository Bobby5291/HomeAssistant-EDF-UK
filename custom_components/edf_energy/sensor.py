# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging

from homeassistant.core import HomeAssistant

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
from .gas.current_rate import EDFEnergyGasCurrentRate
from .gas.next_rate import EDFEnergyGasNextRate
from .gas.previous_rate import EDFEnergyGasPreviousRate
from .gas.standing_charge import EDFEnergyGasCurrentStandingCharge
from .gas.previous_consumption import (
    EDFEnergyPreviousAccumulativeGasConsumption,
    EDFEnergyPreviousAccumulativeGasCost,
)
from .account.balance import (
    EDFEnergyAccountBalance,
    EDFEnergyProjectedBalance,
    EDFEnergyOverdueBalance,
    EDFEnergyRecommendedBalanceAdjustment,
)
from .account.tariff import EDFEnergyElectricityTariff

from .const import (
    CONFIG_ACCOUNT_ID,
    CONFIG_MAIN_SUPPORTS_LIVE_CONSUMPTION,
    CONFIG_MAIN_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
    CONFIG_DEFAULT_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
    DATA_ACCOUNT,
    DATA_ACCOUNT_COORDINATOR,
    DATA_CLIENT,
    DATA_CURRENT_CONSUMPTION_COORDINATOR_KEY,
    DATA_ELECTRICITY_RATES_COORDINATOR_KEY,
    DATA_ELECTRICITY_STANDING_CHARGE_COORDINATOR_KEY,
    DATA_GAS_RATES_COORDINATOR_KEY,
    DATA_GAS_STANDING_CHARGE_COORDINATOR_KEY,
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
                consumption_coordinator_key = DATA_CURRENT_CONSUMPTION_COORDINATOR_KEY.format(device_id)
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

    # -------------------------------------------------------------------------
    # Gas meter sensors — one set per active meter
    # -------------------------------------------------------------------------
    for point in account_info.get("gas_meter_points", []) or []:
        mprn = point["mprn"]

        for meter in point["meters"]:
            serial_number = meter["serial_number"]

            gas_rates_coordinator_key = DATA_GAS_RATES_COORDINATOR_KEY.format(mprn, serial_number)
            gas_standing_charge_coordinator_key = DATA_GAS_STANDING_CHARGE_COORDINATOR_KEY.format(mprn, serial_number)
            gas_previous_consumption_coordinator_key = DATA_PREVIOUS_CONSUMPTION_COORDINATOR_KEY.format(mprn, serial_number)

            gas_rates_coordinator = hass.data[DOMAIN][account_id].get(gas_rates_coordinator_key)
            gas_standing_charge_coordinator = hass.data[DOMAIN][account_id].get(gas_standing_charge_coordinator_key)
            gas_previous_consumption_coordinator = hass.data[DOMAIN][account_id].get(gas_previous_consumption_coordinator_key)

            if gas_rates_coordinator is None:
                _LOGGER.warning(f"Gas rates coordinator not found for {mprn}/{serial_number} — skipping gas rate sensors")
                continue

            entities.append(EDFEnergyGasCurrentRate(hass, gas_rates_coordinator, meter, point))
            entities.append(EDFEnergyGasNextRate(hass, gas_rates_coordinator, meter, point))
            entities.append(EDFEnergyGasPreviousRate(hass, gas_rates_coordinator, meter, point))

            if gas_standing_charge_coordinator is not None:
                entities.append(EDFEnergyGasCurrentStandingCharge(hass, gas_standing_charge_coordinator, meter, point))

            if gas_previous_consumption_coordinator is not None:
                entities.append(EDFEnergyPreviousAccumulativeGasConsumption(hass, gas_previous_consumption_coordinator, meter, point))
                entities.append(EDFEnergyPreviousAccumulativeGasCost(hass, gas_previous_consumption_coordinator, meter, point))

    async_add_entities(entities)
