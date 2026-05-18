# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging
from ..utils.conversions import pence_to_pounds_pence, pence_to_pounds_pence_accurate, consumption_cost_in_pence

_LOGGER = logging.getLogger(__name__)


def __get_to(item):
    return (item["end"].timestamp(), item["end"].fold)


def __sort_consumption(consumption_data):
    sorted_data = consumption_data.copy()
    sorted_data.sort(key=__get_to)
    return sorted_data


def calculate_electricity_consumption_and_cost(
    consumption_data,
    rate_data,
    standing_charge,
    last_reset,
    minimum_consumption_records=0,
):
    if (consumption_data is not None and
            len(consumption_data) >= minimum_consumption_records and
            rate_data is not None and
            len(rate_data) > 0 and
            standing_charge is not None):

        sorted_consumption_data = __sort_consumption(consumption_data)

        if last_reset is None or last_reset < sorted_consumption_data[0]["start"]:
            charges = []
            total_cost_in_pence = 0
            total_consumption = 0

            for consumption in sorted_consumption_data:
                consumption_value = consumption["consumption"]
                consumption_from = consumption["start"]
                consumption_to = consumption["end"]

                try:
                    rate = next(r for r in rate_data if r["start"] == consumption_from and r["end"] == consumption_to)
                except StopIteration:
                    raise Exception(f"Failed to find rate for consumption between {consumption_from} and {consumption_to}")

                value = rate["value_inc_vat"]
                total_consumption += consumption_value
                cost = pence_to_pounds_pence(consumption_cost_in_pence(consumption_value, value))
                raw_cost = consumption_value * value
                total_cost_in_pence += raw_cost

                charges.append({
                    "start": rate["start"],
                    "end": rate["end"],
                    "rate": pence_to_pounds_pence_accurate(value),
                    "consumption": consumption_value,
                    "cost": cost,
                    "raw_cost": pence_to_pounds_pence_accurate(raw_cost),
                })

            total_cost_inc_standing = total_cost_in_pence + standing_charge

            return {
                "standing_charge": pence_to_pounds_pence(standing_charge),
                "total_cost_without_standing_charge": pence_to_pounds_pence(total_cost_in_pence),
                "total_cost": pence_to_pounds_pence(total_cost_inc_standing),
                "total_consumption": total_consumption,
                "last_reset": sorted_consumption_data[0]["start"],
                "last_evaluated": sorted_consumption_data[-1]["end"],
                "charges": charges,
            }
        else:
            _LOGGER.debug(f'Skipping calculation — last_reset has not changed: {last_reset}')
    else:
        _LOGGER.debug(f'Skipping calculation — insufficient data: consumption={len(consumption_data) if consumption_data else 0}, rates={len(rate_data) if rate_data else 0}, standing_charge={standing_charge}')
