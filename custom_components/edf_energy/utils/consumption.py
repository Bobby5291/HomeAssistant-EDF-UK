# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291  — adapted for EDF Energy / Kraken API

from datetime import datetime
import logging

from ..coordinators.current_consumption import CurrentConsumptionCoordinatorResult

_LOGGER = logging.getLogger(__name__)


def get_total_consumption(consumption: list | None):
    total = 0
    if consumption is not None:
        for item in consumption:
            total += item["consumption"]
    return total


def get_current_consumption_delta(current_datetime: datetime, current_total: float, previous_updated: datetime, previous_total: float):
    if previous_total is None or previous_updated is None:
        return None
    if current_datetime.date() == previous_updated.date():
        return current_total - previous_total
    return current_total


class CurrentConsumption:
    def __init__(self, state: float, total_consumption: float, last_evaluated: datetime, data_last_retrieved: datetime):
        self.state = state
        self.total_consumption = total_consumption
        self.last_evaluated = last_evaluated
        self.data_last_retrieved = data_last_retrieved


def calculate_current_consumption(
    current_date: datetime,
    consumption_result: CurrentConsumptionCoordinatorResult,
    current_state: float,
    last_update: datetime,
    last_total_consumption: float,
):
    last_evaluated = last_update
    new_state = current_state
    data_last_evaluated = consumption_result.last_evaluated if consumption_result is not None else None
    consumption_data = consumption_result.data if consumption_result is not None else None
    total_consumption = last_total_consumption

    if consumption_data is not None:
        if last_update is None or consumption_result.last_evaluated > last_update:
            total_consumption = get_total_consumption(consumption_data)
            new_state = get_current_consumption_delta(current_date, total_consumption, last_update, last_total_consumption)
            if new_state is not None:
                last_evaluated = current_date
                data_last_evaluated = consumption_result.last_evaluated
            last_total_consumption = total_consumption
        elif consumption_result.last_evaluated.date() != current_date.date():
            new_state = 0
            last_evaluated = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
            total_consumption = 0

        _LOGGER.debug(f'state: {new_state}; total_consumption: {total_consumption}')

    return CurrentConsumption(new_state, total_consumption, last_evaluated, data_last_evaluated)
