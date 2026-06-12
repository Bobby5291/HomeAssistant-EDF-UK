# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging

from homeassistant.core import HomeAssistant

from .electricity.current_rate import EDFEnergyElectricityCurrentRate
from .electricity.next_rate import EDFEnergyElectricityNextRate
from .electricity.previous_rate import EDFEnergyElectricityPreviousRate
from .electricity.standing_charge import EDFEnergyElectricityCurrentStandingCharge
from .electricity.day_night_rates import EDFEnergyElectricityDayRate, EDFEnergyElectricityNightRate
from .electricity.annual_consumption import (
    EDFEnergyElectricityEACStandard,
    EDFEnergyElectricityEACDay,
    EDFEnergyElectricityEACNight,
)
from .electricity.current_sensors import (
    EDFEnergyCurrentElectricityConsumption,
    EDFEnergyCurrentElectricityDemand,
    EDFEnergyCurrentTotalElectricityConsumption,
    EDFEnergyCurrentAccumulativeElectricityConsumption,
    EDFEnergyCurrentAccumulativeElectricityCost,
)
from .electricity.current_total_export import EDFEnergyCurrentTotalElectricityExport
from .electricity.dynamic_rates import (
    EDFEnergyDynamicCurrentPeriod,
    EDFEnergyDynamicTodayGreenRate,
    EDFEnergyDynamicTodayAmberRate,
    EDFEnergyDynamicTodayRedRate,
    EDFEnergyDynamicTomorrowGreenRate,
    EDFEnergyDynamicTomorrowAmberRate,
    EDFEnergyDynamicTomorrowRedRate,
)
from .utils import get_active_tariff
from .electricity.previous_consumption import (
    EDFEnergyPreviousAccumulativeElectricityConsumption,
    EDFEnergyPreviousAccumulativeElectricityCost,
    EDFEnergyPreviousElectricityPeakConsumption,
    EDFEnergyPreviousElectricityOffPeakConsumption,
    EDFEnergyPreviousElectricityPeakCost,
    EDFEnergyPreviousElectricityOffPeakCost,
)
from .electricity.diagnostics import (
    EDFEnergyElectricityRatesLastRetrieved,
    EDFEnergyElectricityStandingChargeLastRetrieved,
    EDFEnergyElectricityConsumptionLastRetrieved,
)
from .electricity.cost_tracker import (
    EDFEnergyElectricityDailyCost,
    EDFEnergyElectricityWeeklyCost,
    EDFEnergyElectricityMonthlyCost,
)
from .gas.current_rate import EDFEnergyGasCurrentRate
from .gas.next_rate import EDFEnergyGasNextRate
from .gas.previous_rate import EDFEnergyGasPreviousRate
from .gas.standing_charge import EDFEnergyGasCurrentStandingCharge
from .gas.previous_consumption import (
    EDFEnergyPreviousAccumulativeGasConsumption,
    EDFEnergyPreviousAccumulativeGasCost,
)
from .gas.previous_consumption_m3 import EDFEnergyPreviousAccumulativeGasConsumptionM3
from .gas.annual_consumption import EDFEnergyGasAnnualQuantity
from .gas.diagnostics import (
    EDFEnergyGasRatesLastRetrieved,
    EDFEnergyGasStandingChargeLastRetrieved,
    EDFEnergyGasConsumptionLastRetrieved,
)
from .gas.cost_tracker import (
    EDFEnergyGasDailyCost,
    EDFEnergyGasWeeklyCost,
    EDFEnergyGasMonthlyCost,
)
from .account.balance import (
    EDFEnergyAccountBalance,
    EDFEnergyProjectedBalance,
    EDFEnergyOverdueBalance,
    EDFEnergyRecommendedBalanceAdjustment,
)
from .account.tariff import EDFEnergyElectricityTariff, EDFEnergyElectricityTariffType
from .account.contract import (
    EDFEnergyElectricityContractEnd,
    EDFEnergyGasContractEnd,
)
from .account.payment import EDFEnergyDirectDebitAmount, EDFEnergyLastPayment
from .account.diagnostics import EDFEnergyAccountLastRetrieved
from .electricity.meter_reading import EDFEnergyElectricityMeterReading
from .gas.meter_reading import EDFEnergyGasMeterReading
from .intelligent.sensors import (
    EDFEnergyIntelligentCurrentStateSensor,
    EDFEnergyIntelligentDispatchesLastRetrieved,
)

from .const import (
    CONFIG_ACCOUNT_ID,
    CONFIG_MAIN_SUPPORTS_LIVE_CONSUMPTION,
    CONFIG_MAIN_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
    CONFIG_DEFAULT_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
    DATA_ACCOUNT,
    DATA_ACCOUNT_COORDINATOR,
    DATA_CLIENT,
    DATA_ANNUAL_ELECTRICITY_CONSUMPTION_COORDINATOR_KEY,
    DATA_ANNUAL_GAS_CONSUMPTION_COORDINATOR_KEY,
    DATA_ACCOUNT_TRANSACTIONS_COORDINATOR_KEY,
    DATA_CURRENT_CONSUMPTION_COORDINATOR_KEY,
    DATA_ELECTRICITY_COST_TRACKER_COORDINATOR_KEY,
    DATA_ELECTRICITY_METER_READINGS_COORDINATOR_KEY,
    DATA_ELECTRICITY_RATES_COORDINATOR_KEY,
    DATA_ELECTRICITY_STANDING_CHARGE_COORDINATOR_KEY,
    DATA_GAS_COST_TRACKER_COORDINATOR_KEY,
    DATA_GAS_METER_READINGS_COORDINATOR_KEY,
    DATA_GAS_RATES_COORDINATOR_KEY,
    DATA_GAS_STANDING_CHARGE_COORDINATOR_KEY,
    DATA_PREVIOUS_CONSUMPTION_COORDINATOR_KEY,
    DATA_INTELLIGENT_COORDINATOR_KEY,
    DATA_INTELLIGENT_DEVICE_KEY,
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
    # Account-level sensors
    # -------------------------------------------------------------------------
    entities.append(EDFEnergyAccountBalance(hass, account_coordinator, account_id))
    entities.append(EDFEnergyProjectedBalance(hass, account_coordinator, account_id))
    entities.append(EDFEnergyOverdueBalance(hass, account_coordinator, account_id))
    entities.append(EDFEnergyRecommendedBalanceAdjustment(hass, account_coordinator, account_id))
    entities.append(EDFEnergyDirectDebitAmount(hass, account_coordinator, account_id))
    entities.append(EDFEnergyAccountLastRetrieved(hass, account_coordinator, account_id))

    # Last payment (from transactions coordinator)
    transactions_coordinator_key = DATA_ACCOUNT_TRANSACTIONS_COORDINATOR_KEY.format(account_id)
    transactions_coordinator = hass.data[DOMAIN][account_id].get(transactions_coordinator_key)
    if transactions_coordinator is not None:
        entities.append(EDFEnergyLastPayment(hass, transactions_coordinator, account_id))

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

        # Per-MPAN sensors
        entities.append(EDFEnergyElectricityTariff(hass, account_coordinator, account_id, mpan))
        entities.append(EDFEnergyElectricityTariffType(hass, account_coordinator, account_id, mpan))
        entities.append(EDFEnergyElectricityContractEnd(hass, account_coordinator, account_id, mpan))

        annual_elec_coordinator_key = DATA_ANNUAL_ELECTRICITY_CONSUMPTION_COORDINATOR_KEY.format(mpan)
        annual_elec_coordinator = hass.data[DOMAIN][account_id].get(annual_elec_coordinator_key)
        if annual_elec_coordinator is not None:
            entities.append(EDFEnergyElectricityEACStandard(hass, annual_elec_coordinator, mpan))
            entities.append(EDFEnergyElectricityEACDay(hass, annual_elec_coordinator, mpan))
            entities.append(EDFEnergyElectricityEACNight(hass, annual_elec_coordinator, mpan))

        for meter in point["meters"]:
            serial_number = meter["serial_number"]
            device_id = meter.get("device_id")

            rates_coordinator_key = DATA_ELECTRICITY_RATES_COORDINATOR_KEY.format(mpan, serial_number)
            standing_charge_coordinator_key = DATA_ELECTRICITY_STANDING_CHARGE_COORDINATOR_KEY.format(mpan, serial_number)
            previous_consumption_coordinator_key = DATA_PREVIOUS_CONSUMPTION_COORDINATOR_KEY.format(mpan, serial_number)
            readings_coordinator_key = DATA_ELECTRICITY_METER_READINGS_COORDINATOR_KEY.format(mpan, serial_number)
            cost_tracker_coordinator_key = DATA_ELECTRICITY_COST_TRACKER_COORDINATOR_KEY.format(mpan, serial_number)

            rates_coordinator = hass.data[DOMAIN][account_id].get(rates_coordinator_key)
            standing_charge_coordinator = hass.data[DOMAIN][account_id].get(standing_charge_coordinator_key)
            previous_consumption_coordinator = hass.data[DOMAIN][account_id].get(previous_consumption_coordinator_key)
            readings_coordinator = hass.data[DOMAIN][account_id].get(readings_coordinator_key)
            cost_tracker_coordinator = hass.data[DOMAIN][account_id].get(cost_tracker_coordinator_key)

            if rates_coordinator is None:
                _LOGGER.warning(f"Rates coordinator not found for {mpan}/{serial_number} — skipping rate sensors")
                continue

            # Rate sensors (always)
            entities.append(EDFEnergyElectricityCurrentRate(hass, rates_coordinator, meter, point))
            entities.append(EDFEnergyElectricityNextRate(hass, rates_coordinator, meter, point))
            entities.append(EDFEnergyElectricityPreviousRate(hass, rates_coordinator, meter, point))
            entities.append(EDFEnergyElectricityRatesLastRetrieved(hass, rates_coordinator, meter, point))

            # Detect whether this meter is on a Free Phase Dynamic tariff
            _active_tariff = get_active_tariff(
                __import__("homeassistant.util.dt", fromlist=["utcnow"]).utcnow(),
                point.get("agreements", []),
            )
            _tariff_code = _active_tariff.code.upper() if _active_tariff else ""
            _display_name = ""
            for _agr in point.get("agreements", []):
                _dn = str(_agr.get("display_name", "") or "").upper()
                if _dn:
                    _display_name = _dn
                    break
            _DYNAMIC_KW = ("FREEPHASE", "FREE_PHASE", "FREE-PHASE")
            _is_free_phase_dynamic = any(
                kw in _tariff_code or kw in _display_name for kw in _DYNAMIC_KW
            )

            if _is_free_phase_dynamic:
                # Free Phase Dynamic: colour-coded period sensors replace day/night
                entities.append(EDFEnergyDynamicCurrentPeriod(hass, rates_coordinator, meter, point))
                entities.append(EDFEnergyDynamicTodayGreenRate(hass, rates_coordinator, meter, point))
                entities.append(EDFEnergyDynamicTodayAmberRate(hass, rates_coordinator, meter, point))
                entities.append(EDFEnergyDynamicTodayRedRate(hass, rates_coordinator, meter, point))
                entities.append(EDFEnergyDynamicTomorrowGreenRate(hass, rates_coordinator, meter, point))
                entities.append(EDFEnergyDynamicTomorrowAmberRate(hass, rates_coordinator, meter, point))
                entities.append(EDFEnergyDynamicTomorrowRedRate(hass, rates_coordinator, meter, point))
            else:
                # All other tariffs: standard day/night sensors
                entities.append(EDFEnergyElectricityDayRate(hass, rates_coordinator, meter, point))
                entities.append(EDFEnergyElectricityNightRate(hass, rates_coordinator, meter, point))

            # Standing charge
            if standing_charge_coordinator is not None:
                entities.append(EDFEnergyElectricityCurrentStandingCharge(hass, standing_charge_coordinator, meter, point))
                entities.append(EDFEnergyElectricityStandingChargeLastRetrieved(hass, standing_charge_coordinator, meter, point))

            # Meter register reading
            if readings_coordinator is not None:
                entities.append(EDFEnergyElectricityMeterReading(hass, readings_coordinator, meter, point))

            # Previous day consumption + cost + peak/off-peak split
            if previous_consumption_coordinator is not None:
                entities.append(EDFEnergyPreviousAccumulativeElectricityConsumption(hass, previous_consumption_coordinator, meter, point))
                entities.append(EDFEnergyPreviousAccumulativeElectricityCost(hass, previous_consumption_coordinator, meter, point))
                entities.append(EDFEnergyPreviousElectricityPeakConsumption(hass, previous_consumption_coordinator, meter, point))
                entities.append(EDFEnergyPreviousElectricityOffPeakConsumption(hass, previous_consumption_coordinator, meter, point))
                entities.append(EDFEnergyPreviousElectricityPeakCost(hass, previous_consumption_coordinator, meter, point))
                entities.append(EDFEnergyPreviousElectricityOffPeakCost(hass, previous_consumption_coordinator, meter, point))
                entities.append(EDFEnergyElectricityConsumptionLastRetrieved(hass, previous_consumption_coordinator, meter, point))

            # Daily/weekly/monthly cost trackers
            if cost_tracker_coordinator is not None:
                entities.append(EDFEnergyElectricityDailyCost(hass, cost_tracker_coordinator, meter, point))
                entities.append(EDFEnergyElectricityWeeklyCost(hass, cost_tracker_coordinator, meter, point))
                entities.append(EDFEnergyElectricityMonthlyCost(hass, cost_tracker_coordinator, meter, point))

            # Live smart meter sensors — only if user has SMETS2 and opted in
            if supports_live and device_id is not None:
                consumption_coordinator_key = DATA_CURRENT_CONSUMPTION_COORDINATOR_KEY.format(device_id)
                consumption_coordinator = hass.data[DOMAIN][account_id].get(consumption_coordinator_key)

                if consumption_coordinator is not None:
                    entities.append(EDFEnergyCurrentElectricityConsumption(hass, consumption_coordinator, meter, point))
                    entities.append(EDFEnergyCurrentElectricityDemand(hass, consumption_coordinator, meter, point))
                    entities.append(EDFEnergyCurrentTotalElectricityConsumption(hass, consumption_coordinator, meter, point))
                    entities.append(EDFEnergyCurrentTotalElectricityExport(hass, consumption_coordinator, meter, point))

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

        # Per-MPRN sensors
        entities.append(EDFEnergyGasContractEnd(hass, account_coordinator, account_id, mprn))

        annual_gas_coordinator_key = DATA_ANNUAL_GAS_CONSUMPTION_COORDINATOR_KEY.format(mprn)
        annual_gas_coordinator = hass.data[DOMAIN][account_id].get(annual_gas_coordinator_key)
        if annual_gas_coordinator is not None:
            entities.append(EDFEnergyGasAnnualQuantity(hass, annual_gas_coordinator, mprn))

        for meter in point["meters"]:
            serial_number = meter["serial_number"]

            gas_rates_coordinator_key = DATA_GAS_RATES_COORDINATOR_KEY.format(mprn, serial_number)
            gas_standing_charge_coordinator_key = DATA_GAS_STANDING_CHARGE_COORDINATOR_KEY.format(mprn, serial_number)
            gas_previous_consumption_coordinator_key = DATA_PREVIOUS_CONSUMPTION_COORDINATOR_KEY.format(mprn, serial_number)
            gas_readings_coordinator_key = DATA_GAS_METER_READINGS_COORDINATOR_KEY.format(mprn, serial_number)
            gas_cost_tracker_coordinator_key = DATA_GAS_COST_TRACKER_COORDINATOR_KEY.format(mprn, serial_number)

            gas_rates_coordinator = hass.data[DOMAIN][account_id].get(gas_rates_coordinator_key)
            gas_standing_charge_coordinator = hass.data[DOMAIN][account_id].get(gas_standing_charge_coordinator_key)
            gas_previous_consumption_coordinator = hass.data[DOMAIN][account_id].get(gas_previous_consumption_coordinator_key)
            gas_readings_coordinator = hass.data[DOMAIN][account_id].get(gas_readings_coordinator_key)
            gas_cost_tracker_coordinator = hass.data[DOMAIN][account_id].get(gas_cost_tracker_coordinator_key)

            if gas_rates_coordinator is None:
                _LOGGER.warning(f"Gas rates coordinator not found for {mprn}/{serial_number} — skipping gas rate sensors")
                continue

            entities.append(EDFEnergyGasCurrentRate(hass, gas_rates_coordinator, meter, point))
            entities.append(EDFEnergyGasNextRate(hass, gas_rates_coordinator, meter, point))
            entities.append(EDFEnergyGasPreviousRate(hass, gas_rates_coordinator, meter, point))
            entities.append(EDFEnergyGasRatesLastRetrieved(hass, gas_rates_coordinator, meter, point))

            if gas_standing_charge_coordinator is not None:
                entities.append(EDFEnergyGasCurrentStandingCharge(hass, gas_standing_charge_coordinator, meter, point))
                entities.append(EDFEnergyGasStandingChargeLastRetrieved(hass, gas_standing_charge_coordinator, meter, point))

            if gas_previous_consumption_coordinator is not None:
                entities.append(EDFEnergyPreviousAccumulativeGasConsumption(hass, gas_previous_consumption_coordinator, meter, point))
                entities.append(EDFEnergyPreviousAccumulativeGasCost(hass, gas_previous_consumption_coordinator, meter, point))
                entities.append(EDFEnergyPreviousAccumulativeGasConsumptionM3(hass, gas_previous_consumption_coordinator, meter, point))
                entities.append(EDFEnergyGasConsumptionLastRetrieved(hass, gas_previous_consumption_coordinator, meter, point))

            if gas_readings_coordinator is not None:
                entities.append(EDFEnergyGasMeterReading(hass, gas_readings_coordinator, meter, point))

            if gas_cost_tracker_coordinator is not None:
                entities.append(EDFEnergyGasDailyCost(hass, gas_cost_tracker_coordinator, meter, point))
                entities.append(EDFEnergyGasWeeklyCost(hass, gas_cost_tracker_coordinator, meter, point))
                entities.append(EDFEnergyGasMonthlyCost(hass, gas_cost_tracker_coordinator, meter, point))

    async_add_entities(entities)
