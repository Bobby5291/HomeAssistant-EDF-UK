# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291  — adapted for EDF Energy / Kraken API

import re
from datetime import datetime

from homeassistant.util.dt import as_local

attribute_keys_to_skip = ['mpan', 'mprn']
default_keys_to_ignore = ['last_evaluated', 'data_last_retrieved', 'total_cost_without_standing_charge']


def dict_to_typed_dict(data: dict, keys_to_ignore=[]):
    """Convert a dict of strings to properly typed values (int, float, datetime)."""
    if data is None:
        return None

    if not isinstance(data, dict):
        return data

    new_data = data.copy()
    keys = list(new_data.keys())

    for key in keys:
        if key in keys_to_ignore or key in default_keys_to_ignore:
            del new_data[key]
            continue

        if isinstance(new_data[key], str) and key not in attribute_keys_to_skip:
            if re.search("^[0-9]+$", new_data[key]):
                new_data[key] = int(new_data[key])
                continue

            if re.search("^[0-9]+\\.[0-9]+$", new_data[key]):
                new_data[key] = float(new_data[key])
                continue

            try:
                data_as_datetime = datetime.fromisoformat(new_data[key].replace('Z', '+00:00'))
                new_data[key] = as_local(data_as_datetime)
                continue
            except Exception:
                pass

        elif isinstance(new_data[key], dict):
            new_data[key] = dict_to_typed_dict(new_data[key])
        elif isinstance(new_data[key], list):
            new_data[key] = [dict_to_typed_dict(item) for item in new_data[key]]
        elif isinstance(new_data[key], datetime):
            new_data[key] = as_local(new_data[key])

    return new_data
