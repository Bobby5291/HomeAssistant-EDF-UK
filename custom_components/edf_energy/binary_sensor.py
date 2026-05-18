# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 2026 — adapted for EDF Energy / Kraken API

import logging

from homeassistant.core import HomeAssistant

from .account.balance import (
    EDFEnergyAccountIsOverdue,
    EDFEnergyDirectDebitNeedsReview,
)

from .const import (
    CONFIG_ACCOUNT_ID,
    DATA_ACCOUNT,
    DATA_ACCOUNT_COORDINATOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up EDF Energy binary sensors from a config entry."""
    config = dict(entry.data)
    account_id = config[CONFIG_ACCOUNT_ID]

    account_coordinator = hass.data[DOMAIN][account_id][DATA_ACCOUNT_COORDINATOR]

    entities = [
        EDFEnergyAccountIsOverdue(hass, account_coordinator, account_id),
        EDFEnergyDirectDebitNeedsReview(hass, account_coordinator, account_id),
    ]

    async_add_entities(entities)
