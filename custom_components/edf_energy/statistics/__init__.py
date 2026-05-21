# Bobby5291 2026 — EDF Energy / Kraken API — HA Statistics helpers

import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData
from homeassistant.components.recorder.statistics import statistics_during_period

from ..utils.conversions import consumption_cost_in_pence, pence_to_pounds_pence

_LOGGER = logging.getLogger(__name__)


async def async_get_last_statistic_sum(hass: HomeAssistant, before: datetime, statistic_id: str) -> float:
    """Return the most recent cumulative sum before *before*, or 0 if none."""
    results = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        before - timedelta(days=7),
        before,
        {statistic_id},
        "hour",
        None,
        {"sum"},
    )
    if statistic_id in results and results[statistic_id]:
        return results[statistic_id][-1]["sum"] or 0
    return 0


def build_consumption_statistics(
    consumptions: list,
    rates: list,
    consumption_key: str,
    initial_sum: float,
    target_rate_value=None,
) -> list:
    """Build a list of StatisticData (hourly) from half-hourly consumption + rate data.

    Pairs consecutive half-hour slots into one-hour buckets (index % 2 == 1).
    Only includes consumption where the rate matches *target_rate_value* (or all
    consumption when *target_rate_value* is None).
    """
    if not consumptions or not rates:
        return []

    last_reset = consumptions[0]["start"].replace(minute=0, second=0, microsecond=0)
    running_sum = initial_sum
    running_state = 0.0
    statistics = []

    for idx, consumption in enumerate(consumptions):
        c_start = consumption["start"]
        c_end = consumption["end"]

        rate = next(
            (r for r in rates if r["start"] == c_start and r["end"] == c_end),
            None,
        )
        if rate is None:
            _LOGGER.debug(f"No rate found for consumption slot {c_start}–{c_end}, skipping")
            continue

        if target_rate_value is None or target_rate_value == rate["value_inc_vat"]:
            value = consumption[consumption_key]
            running_sum += value
            running_state += value

        # Emit one statistic per hour (after every second slot)
        if idx % 2 == 1:
            bucket_start = c_start.replace(minute=0, second=0, microsecond=0)
            statistics.append(
                StatisticData(
                    start=bucket_start,
                    last_reset=last_reset,
                    sum=running_sum,
                    state=running_state,
                )
            )
            running_state = 0.0

    return statistics


def build_cost_statistics(
    consumptions: list,
    rates: list,
    consumption_key: str,
    initial_sum: float,
    target_rate_value=None,
) -> list:
    """Build cost StatisticData (GBP) from half-hourly consumption + rate data."""
    if not consumptions or not rates:
        return []

    last_reset = consumptions[0]["start"].replace(minute=0, second=0, microsecond=0)
    running_sum = initial_sum
    running_state = 0.0
    statistics = []

    for idx, consumption in enumerate(consumptions):
        c_start = consumption["start"]
        c_end = consumption["end"]

        rate = next(
            (r for r in rates if r["start"] == c_start and r["end"] == c_end),
            None,
        )
        if rate is None:
            continue

        if target_rate_value is None or target_rate_value == rate["value_inc_vat"]:
            cost_gbp = pence_to_pounds_pence(
                consumption_cost_in_pence(consumption[consumption_key], rate["value_inc_vat"])
            )
            running_sum += cost_gbp
            running_state += cost_gbp

        if idx % 2 == 1:
            bucket_start = c_start.replace(minute=0, second=0, microsecond=0)
            statistics.append(
                StatisticData(
                    start=bucket_start,
                    last_reset=last_reset,
                    sum=running_sum,
                    state=running_state,
                )
            )
            running_state = 0.0

    return statistics
