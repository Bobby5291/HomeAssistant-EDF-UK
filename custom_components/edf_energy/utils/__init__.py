# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291  — adapted for EDF Energy / Kraken API

import logging
import re
from datetime import datetime, timedelta

from homeassistant.util.dt import as_local, as_utc, parse_datetime

from ..const import REGEX_TARIFF_PARTS
from ..utils.conversions import pence_to_pounds_pence_accurate
from .rate_information import get_current_rate_information

_LOGGER = logging.getLogger(__name__)


class TariffParts:
    energy: str
    rate: str
    product_code: str
    region: str

    def __init__(self, energy: str, rate: str, product_code: str, region: str):
        self.energy = energy
        self.rate = rate
        self.product_code = product_code
        self.region = region


def get_tariff_parts(tariff_code: str) -> TariffParts:
    matches = re.search(REGEX_TARIFF_PARTS, tariff_code)
    if matches is None:
        return None

    energy = matches.groupdict()["energy"] or "E"
    rate = matches.groupdict()["rate"] or "1R"
    product_code = matches.groupdict()["product_code"]
    region = matches.groupdict()["region"]

    return TariffParts(energy, rate, product_code, region)


class Tariff:
    product: str
    code: str

    def __init__(self, product: str, code: str):
        self.product = product
        self.code = code


def get_active_tariff(utcnow: datetime, agreements):
    """Find the currently active tariff from a list of agreements."""
    latest_agreement = None
    latest_valid_from = None

    if not agreements:
        _LOGGER.warning("get_active_tariff called with empty agreements list")
        return None

    for agreement in agreements:
        if agreement["tariff_code"] is None:
            continue

        valid_from = as_utc(parse_datetime(agreement["start"]))

        if utcnow >= valid_from and (latest_valid_from is None or valid_from > latest_valid_from):
            latest_valid_to = None
            if "end" in agreement and agreement["end"] is not None:
                latest_valid_to = as_utc(parse_datetime(agreement["end"]))

            if latest_valid_to is None or latest_valid_to >= utcnow:
                latest_agreement = agreement
                latest_valid_from = valid_from

    if latest_agreement is not None:
        return Tariff(latest_agreement["product_code"], latest_agreement["tariff_code"])

    return None


def private_rates_to_public_rates(rates: list):
    """Convert internal rate format (pence, UTC) to public format (pounds, local time)."""
    if rates is None:
        return None

    new_rates = []
    for rate in rates:
        new_rate = {
            "start": as_local(rate["start"]),
            "end": as_local(rate["end"]),
            "value_inc_vat": pence_to_pounds_pence_accurate(rate["value_inc_vat"]),
        }
        if "is_capped" in rate:
            new_rate["is_capped"] = rate["is_capped"]

        new_rates.append(new_rate)

    return new_rates
