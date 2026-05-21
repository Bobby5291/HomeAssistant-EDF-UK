# Bobby5291 2026 — EDF Energy / Kraken API

from datetime import datetime, timedelta
from homeassistant.util.dt import as_utc, as_local
from ..utils.conversions import pence_to_pounds_pence_accurate


def get_target_rate_info(rates: list, duration_minutes: int, now: datetime, window_hours: int = 24):
    """
    Find the cheapest contiguous block of `duration_minutes` within the next
    `window_hours` hours. Rates must be pre-sorted ascending by start time.

    Returns a dict or None if insufficient rate data exists.
    """
    if not rates or duration_minutes <= 0:
        return None

    slots_needed = duration_minutes // 30
    if slots_needed < 1:
        return None

    window_start = now
    window_end = now + timedelta(hours=window_hours)

    # Filter to the look-ahead window
    window_rates = [
        r for r in rates
        if r["start"] >= window_start and r["end"] <= window_end
    ]
    window_rates.sort(key=lambda r: r["start"])

    if len(window_rates) < slots_needed:
        return None

    best_cost = None
    best_idx = None

    for i in range(len(window_rates) - slots_needed + 1):
        block = window_rates[i:i + slots_needed]
        # Verify slots are truly consecutive with no gaps
        consecutive = all(
            block[j]["end"] == block[j + 1]["start"]
            for j in range(len(block) - 1)
        )
        if not consecutive:
            continue

        avg = sum(r["value_inc_vat"] for r in block) / len(block)
        if best_cost is None or avg < best_cost:
            best_cost = avg
            best_idx = i

    if best_idx is None:
        return None

    best_block = window_rates[best_idx:best_idx + slots_needed]
    target_start = best_block[0]["start"]
    target_end = best_block[-1]["end"]
    is_active = target_start <= now < target_end

    return {
        "target_start": target_start,
        "target_end": target_end,
        "average_rate": pence_to_pounds_pence_accurate(best_cost),
        "min_rate": pence_to_pounds_pence_accurate(min(r["value_inc_vat"] for r in best_block)),
        "max_rate": pence_to_pounds_pence_accurate(max(r["value_inc_vat"] for r in best_block)),
        "is_active": is_active,
        "rates_in_period": [
            {
                "start": r["start"],
                "end": r["end"],
                "value_inc_vat": pence_to_pounds_pence_accurate(r["value_inc_vat"]),
            }
            for r in best_block
        ],
    }
