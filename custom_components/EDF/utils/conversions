# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291  — adapted for EDF Energy / Kraken API

from decimal import ROUND_HALF_EVEN, Decimal


def pence_to_pounds_pence_accurate(value: float):
    """Convert pence to pounds with 6dp accuracy for rate display."""
    return round(value / 100, 6)


def round_pounds(value: float):
    return round(value, 2)


def pence_to_pounds_pence(value: float):
    return round_pounds(value / 100)


def consumption_cost_in_pence(consumption: float, rate: float):
    """Calculate cost in pence, rounding per billing conventions."""
    rounded_consumption = float(Decimal(str(consumption)).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN))
    return rounded_consumption * round(rate, 2)
