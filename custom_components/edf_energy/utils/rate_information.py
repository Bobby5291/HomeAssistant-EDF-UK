# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 — adapted for EDF Energy / Kraken API

from datetime import datetime, timedelta

from homeassistant.util.dt import as_local, as_utc

from ..utils.conversions import pence_to_pounds_pence_accurate


def get_current_rate_information(rates, now: datetime):
    """Get the current rate and today's min/max/average from the rates list."""
    min_target = now.replace(hour=0, minute=0, second=0, microsecond=0)
    max_target = min_target + timedelta(days=1)

    min_rate_value = None
    max_rate_value = None
    total_rate_value = 0
    total_rates = 0
    current_rate = None
    applicable_rates = []
    is_adding_applicable_rates = True

    if rates is not None:
        for period in rates:
            if current_rate is None and len(applicable_rates) > 0 and applicable_rates[0]["value_inc_vat"] != period["value_inc_vat"]:
                applicable_rates.clear()

            if is_adding_applicable_rates and (len(applicable_rates) < 1 or current_rate is None or applicable_rates[0]["value_inc_vat"] == period["value_inc_vat"]):
                applicable_rates.append(period)
            elif current_rate is not None and len(applicable_rates) > 0 and applicable_rates[0]["value_inc_vat"] != period["value_inc_vat"]:
                is_adding_applicable_rates = False

            if now >= period["start"] and now <= period["end"]:
                current_rate = period

            if period["start"] >= min_target and period["end"] <= max_target:
                if min_rate_value is None or period["value_inc_vat"] < min_rate_value:
                    min_rate_value = period["value_inc_vat"]
                if max_rate_value is None or period["value_inc_vat"] > max_rate_value:
                    max_rate_value = period["value_inc_vat"]
                total_rate_value += period["value_inc_vat"]
                total_rates += 1

    if len(applicable_rates) > 0 and current_rate is not None:
        return {
            "all_rates": list(map(lambda x: {
                "start": x["start"],
                "end": x["end"],
                "value_inc_vat": pence_to_pounds_pence_accurate(x["value_inc_vat"]),
                "is_capped": x["is_capped"],
            }, rates)),
            "applicable_rates": list(map(lambda x: {
                "start": x["start"],
                "end": x["end"],
                "value_inc_vat": pence_to_pounds_pence_accurate(x["value_inc_vat"]),
                "is_capped": x["is_capped"],
            }, applicable_rates)),
            "current_rate": {
                "start": applicable_rates[0]["start"],
                "end": applicable_rates[-1]["end"],
                "tariff_code": current_rate["tariff_code"],
                "value_inc_vat": pence_to_pounds_pence_accurate(applicable_rates[0]["value_inc_vat"]),
                "is_capped": current_rate["is_capped"],
            },
            "min_rate_today": pence_to_pounds_pence_accurate(min_rate_value),
            "max_rate_today": pence_to_pounds_pence_accurate(max_rate_value),
            "average_rate_today": pence_to_pounds_pence_accurate(total_rate_value / total_rates) if total_rates > 0 else None,
        }

    return None


def get_next_rate_information(rates, now: datetime):
    """Get the next rate period after the current one."""
    current_rate = None
    applicable_rates = []

    if rates is not None:
        for period in rates:
            if now >= period["start"] and now <= period["end"]:
                current_rate = period
                continue

            if current_rate is not None and current_rate["value_inc_vat"] != period["value_inc_vat"]:
                if len(applicable_rates) == 0 or period["value_inc_vat"] == applicable_rates[0]["value_inc_vat"]:
                    applicable_rates.append(period)
                else:
                    break
            elif len(applicable_rates) > 0:
                break

    if len(applicable_rates) > 0 and current_rate is not None:
        return {
            "applicable_rates": list(map(lambda x: {
                "start": x["start"],
                "end": x["end"],
                "value_inc_vat": pence_to_pounds_pence_accurate(x["value_inc_vat"]),
                "is_capped": x["is_capped"],
            }, applicable_rates)),
            "next_rate": {
                "start": applicable_rates[0]["start"],
                "end": applicable_rates[-1]["end"],
                "value_inc_vat": pence_to_pounds_pence_accurate(applicable_rates[0]["value_inc_vat"]),
            },
        }

    return None


def get_previous_rate_information(rates, now: datetime):
    """Get the previous rate period before the current one."""
    current_rate = None
    applicable_rates = []

    if rates is not None:
        for period in reversed(rates):
            if now >= period["start"] and now <= period["end"]:
                current_rate = period
                continue

            if current_rate is not None and current_rate["value_inc_vat"] != period["value_inc_vat"]:
                if len(applicable_rates) == 0 or period["value_inc_vat"] == applicable_rates[0]["value_inc_vat"]:
                    applicable_rates.append(period)
                else:
                    break
            elif len(applicable_rates) > 0:
                break

    applicable_rates.sort(key=lambda x: (x["start"].timestamp(), x["start"].fold))

    if len(applicable_rates) > 0 and current_rate is not None:
        return {
            "applicable_rates": list(map(lambda x: {
                "start": x["start"],
                "end": x["end"],
                "value_inc_vat": pence_to_pounds_pence_accurate(x["value_inc_vat"]),
                "is_capped": x["is_capped"],
            }, applicable_rates)),
            "previous_rate": {
                "start": applicable_rates[0]["start"],
                "end": applicable_rates[-1]["end"],
                "value_inc_vat": pence_to_pounds_pence_accurate(applicable_rates[0]["value_inc_vat"]),
            },
        }

    return None


def get_min_max_average_rates(rates: list):
    """Get min, max and average rate values from a list of rates."""
    min_rate = None
    max_rate = None
    average_rate = 0

    if rates is not None:
        for rate in rates:
            if min_rate is None or rate["value_inc_vat"] < min_rate:
                min_rate = rate["value_inc_vat"]
            if max_rate is None or rate["value_inc_vat"] > max_rate:
                max_rate = rate["value_inc_vat"]
            average_rate += rate["value_inc_vat"]

    return {
        "min": min_rate,
        "max": max_rate,
        "average": round(average_rate / len(rates) if rates is not None and len(rates) > 0 else 1, 8),
    }


def get_unique_rates(current: datetime, rates: list):
    """Get unique rate values for today."""
    today_start = as_utc(as_local(current).replace(hour=0, minute=0, second=0, microsecond=0))
    today_end = today_start + timedelta(days=1)

    rate_charges = []
    if rates is not None:
        for rate in rates:
            if rate["start"] >= today_start and rate["end"] <= today_end:
                value = rate["value_inc_vat"]
                if value not in rate_charges:
                    rate_charges.append(value)

    rate_charges.sort()
    return rate_charges


def has_peak_rates(total_unique_rates: int) -> bool:
    """True if the tariff has two or three distinct rate tiers (day/night or three-rate)."""
    return total_unique_rates in (2, 3)


def get_peak_type(total_unique_rates: int, unique_rate_index: int) -> str | None:
    """Return the peak type label for a given rate index (lowest → off_peak)."""
    if not has_peak_rates(total_unique_rates):
        return None
    if unique_rate_index == 0:
        return "off_peak"
    elif unique_rate_index == 1:
        return "peak" if total_unique_rates == 2 else "standard"
    elif unique_rate_index == 2:
        return "peak"
    return None


def get_peak_name(peak_type: str) -> str | None:
    """Human-readable label for a peak type."""
    return {"off_peak": "Off Peak", "peak": "Peak", "standard": "Standard"}.get(peak_type)


def get_off_peak_times(current: datetime, rates: list) -> list:
    """Return a list of (start, end) tuples for off-peak windows in the next 48 h.

    Off-peak is defined as any period whose rate is strictly below today's
    maximum rate.  Returns windows sorted by start time.
    """
    if not rates:
        return []

    window_end = current + timedelta(hours=48)
    today_start = as_utc(as_local(current).replace(hour=0, minute=0, second=0, microsecond=0))
    today_end = today_start + timedelta(days=1)

    # Determine today's max rate to classify off-peak
    max_rate = None
    for r in rates:
        if r["start"] >= today_start and r["end"] <= today_end:
            if max_rate is None or r["value_inc_vat"] > max_rate:
                max_rate = r["value_inc_vat"]

    if max_rate is None:
        return []

    windows = []
    window_start = None

    relevant = [r for r in rates if r["end"] > current and r["start"] < window_end]
    for period in relevant:
        is_off_peak = period["value_inc_vat"] < max_rate
        if is_off_peak and window_start is None:
            window_start = period["start"]
        elif not is_off_peak and window_start is not None:
            windows.append({"start": window_start, "end": period["start"]})
            window_start = None

    if window_start is not None:
        windows.append({"start": window_start, "end": relevant[-1]["end"]})

    return windows
