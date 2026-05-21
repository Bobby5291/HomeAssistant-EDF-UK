# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging

from homeassistant.core import HomeAssistant

from .account.balance import (
    EDFEnergyAccountIsOverdue,
    EDFEnergyDirectDebitNeedsReview,
)
from .account.contract import EDFEnergyCanRenewTariff
from .electricity.target_rate import EDFEnergyElectricityTargetRateBinarySensor
from .electricity.tomorrow_rates import EDFEnergyElectricityNextDayRatesAvailable
from .electricity.off_peak import EDFEnergyElectricityOffPeak
from .intelligent.binary_sensors import EDFEnergyIntelligentOffPeakBinarySensor

from .const import (
    CONFIG_ACCOUNT_ID,
    DATA_ACCOUNT,
    DATA_ACCOUNT_COORDINATOR,
    DATA_ELECTRICITY_RATES_COORDINATOR_KEY,
    DATA_INTELLIGENT_COORDINATOR_KEY,
    DATA_INTELLIGENT_DEVICE_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Cheapest-period durations offered as binary sensors (minutes)
TARGET_RATE_DURATIONS = [60, 120, 180]


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up EDF Energy binary sensors from a config entry."""
    config = dict(entry.data)
    account_id = config[CONFIG_ACCOUNT_ID]

    account_coordinator = hass.data[DOMAIN][account_id][DATA_ACCOUNT_COORDINATOR]

    entities = [
        EDFEnergyAccountIsOverdue(hass, account_coordinator, account_id),
        EDFEnergyDirectDebitNeedsReview(hass, account_coordinator, account_id),
        EDFEnergyCanRenewTariff(hass, account_coordinator, account_id),
    ]

    # Per-meter binary sensors (target rates + tomorrow rates available)
    account_result = hass.data[DOMAIN][account_id].get(DATA_ACCOUNT)
    account_info = account_result.account if account_result is not None else None

    if account_info is not None:
        for point in account_info.get("electricity_meter_points", []) or []:
            for meter in point["meters"]:
                serial_number = meter["serial_number"]
                mpan = point["mpan"]

                rates_coordinator_key = DATA_ELECTRICITY_RATES_COORDINATOR_KEY.format(mpan, serial_number)
                rates_coordinator = hass.data[DOMAIN][account_id].get(rates_coordinator_key)

                if rates_coordinator is None:
                    _LOGGER.warning(
                        f"Rates coordinator not found for {mpan}/{serial_number} "
                        "— skipping target rate and tomorrow rates sensors"
                    )
                    continue

                # Cheapest period binary sensors (1h, 2h, 3h)
                for duration in TARGET_RATE_DURATIONS:
                    entities.append(
                        EDFEnergyElectricityTargetRateBinarySensor(
                            hass, rates_coordinator, meter, point, duration
                        )
                    )

                # Tomorrow's rates available binary sensor
                entities.append(
                    EDFEnergyElectricityNextDayRatesAvailable(hass, rates_coordinator, meter, point)
                )

                # Off-peak binary sensor (rate-based — shows cheapest rate windows)
                entities.append(
                    EDFEnergyElectricityOffPeak(hass, rates_coordinator, meter, point)
                )

    # Intelligent off-peak sensor
    intelligent_device = hass.data[DOMAIN][account_id].get(DATA_INTELLIGENT_DEVICE_KEY.format(account_id))
    if intelligent_device is not None:
        ev_device_id = intelligent_device["id"]
        intelligent_coordinator_key = DATA_INTELLIGENT_COORDINATOR_KEY.format(ev_device_id)
        intelligent_coordinator = hass.data[DOMAIN][account_id].get(intelligent_coordinator_key)
        if intelligent_coordinator is not None:
            entities.append(EDFEnergyIntelligentOffPeakBinarySensor(hass, intelligent_coordinator, account_id, intelligent_device))

    async_add_entities(entities)
