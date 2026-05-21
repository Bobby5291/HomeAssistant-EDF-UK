# Bobby5291 2026 — EDF Energy / Kraken API — Consumption statistics importer

import logging
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.components.recorder.models import StatisticMetaData, StatisticMeanType
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.util.unit_conversion import EnergyConverter, VolumeConverter

from ..const import DOMAIN
from ..utils.rate_information import get_unique_rates, has_peak_rates, get_peak_type, get_peak_name
from . import async_get_last_statistic_sum, build_consumption_statistics

_LOGGER = logging.getLogger(__name__)


def electricity_consumption_statistic_id(serial_number: str, mpan: str, is_export: bool = False) -> str:
    suffix = "_export" if is_export else ""
    return f"{DOMAIN}:electricity_{serial_number}_{mpan}{suffix}_previous_accumulative_consumption".lower()


def electricity_consumption_statistic_name(serial_number: str, mpan: str, is_export: bool = False) -> str:
    suffix = " Export" if is_export else ""
    return f"Electricity {serial_number} {mpan}{suffix} Previous Accumulative Consumption"


def gas_consumption_statistic_id(serial_number: str, mprn: str, is_kwh: bool = True) -> str:
    suffix = "_kwh" if is_kwh else ""
    return f"{DOMAIN}:gas_{serial_number}_{mprn}_previous_accumulative_consumption{suffix}".lower()


def gas_consumption_statistic_name(serial_number: str, mprn: str, is_kwh: bool = True) -> str:
    unit_label = " (kWh)" if is_kwh else " (m³)"
    return f"Gas {serial_number} {mprn} Previous Accumulative Consumption{unit_label}"


async def async_import_consumption_statistics(
    hass: HomeAssistant,
    current: datetime,
    statistic_id: str,
    statistic_name: str,
    consumptions: list,
    rates: list,
    unit_of_measurement: str,
    consumption_key: str = "consumption",
):
    """Import consumption into HA long-term statistics, with peak/off-peak breakdown."""
    if not consumptions or not rates:
        return

    initial_sum = await async_get_last_statistic_sum(hass, consumptions[0]["start"], statistic_id)

    unit_class = (
        EnergyConverter.UNIT_CLASS
        if unit_of_measurement in EnergyConverter.VALID_UNITS
        else VolumeConverter.UNIT_CLASS
        if unit_of_measurement in VolumeConverter.VALID_UNITS
        else None
    )

    stats = build_consumption_statistics(consumptions, rates, consumption_key, initial_sum)
    if not stats:
        return

    async_add_external_statistics(
        hass,
        StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=statistic_name,
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_of_measurement=unit_of_measurement,
            mean_type=StatisticMeanType.NONE,
            unit_class=unit_class,
        ),
        stats,
    )

    unique_rates = get_unique_rates(current, rates)
    if has_peak_rates(len(unique_rates)):
        for idx, rate_val in enumerate(unique_rates):
            peak_type = get_peak_type(len(unique_rates), idx)
            peak_stat_id = f"{statistic_id}_{peak_type}"
            peak_initial = await async_get_last_statistic_sum(hass, consumptions[0]["start"], peak_stat_id)
            peak_stats = build_consumption_statistics(consumptions, rates, consumption_key, peak_initial, target_rate_value=rate_val)
            if not peak_stats:
                continue
            async_add_external_statistics(
                hass,
                StatisticMetaData(
                    has_mean=False,
                    has_sum=True,
                    name=f"{statistic_name} {get_peak_name(peak_type)}",
                    source=DOMAIN,
                    statistic_id=peak_stat_id,
                    unit_of_measurement=unit_of_measurement,
                    mean_type=StatisticMeanType.NONE,
                    unit_class=unit_class,
                ),
                peak_stats,
            )
