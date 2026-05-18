# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 — adapted for EDF Energy / Kraken API

from datetime import datetime, timedelta


def calculate_next_refresh(current: datetime, request_attempts: int, refresh_rate_in_minutes: float):
    """
    Calculate when the next refresh should happen.
    Uses triangular backoff on failures, capped at 30 minute intervals.
    """
    next_rate = current.replace(second=0, microsecond=0) + timedelta(minutes=refresh_rate_in_minutes)

    if request_attempts > 1:
        i = request_attempts - 1
        number_of_additional_thirty_minutes = 0

        if i > 30:
            number_of_additional_thirty_minutes = i - 30
            i = 30

        target_minutes = i * (i + 1) / 2
        next_rate = next_rate + timedelta(minutes=target_minutes)

        if number_of_additional_thirty_minutes > 0:
            next_rate = next_rate + timedelta(minutes=30 * number_of_additional_thirty_minutes)

    return next_rate
