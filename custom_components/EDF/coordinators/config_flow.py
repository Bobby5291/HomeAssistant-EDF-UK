# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by Bobby5291 [year] — adapted for EDF Energy / Kraken API

import voluptuous as vol
import logging

from homeassistant.util.dt import utcnow
from homeassistant.config_entries import ConfigFlow
import homeassistant.helpers.config_validation as cv

from .api_client import EDFEnergyApiClient, AuthenticationException
from .const import (
    CONFIG_ACCOUNT_ID,
    CONFIG_MAIN_EMAIL,
    CONFIG_MAIN_PASSWORD,
    CONFIG_MAIN_CALORIFIC_VALUE,
    CONFIG_MAIN_SUPPORTS_LIVE_CONSUMPTION,
    CONFIG_MAIN_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
    CONFIG_MAIN_LIVE_GAS_CONSUMPTION_REFRESH_IN_MINUTES,
    CONFIG_DEFAULT_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
    CONFIG_DEFAULT_LIVE_GAS_CONSUMPTION_REFRESH_IN_MINUTES,
    CONFIG_VERSION,
    DEFAULT_CALORIFIC_VALUE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def __setup_account_schema__(include_account_id=True):
    schema = {
        vol.Required(CONFIG_MAIN_EMAIL): str,
        vol.Required(CONFIG_MAIN_PASSWORD): str,
        vol.Required(CONFIG_MAIN_CALORIFIC_VALUE, default=DEFAULT_CALORIFIC_VALUE): cv.positive_float,
        vol.Required(CONFIG_MAIN_SUPPORTS_LIVE_CONSUMPTION, default=False): bool,
        vol.Required(
            CONFIG_MAIN_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES,
            default=CONFIG_DEFAULT_LIVE_ELECTRICITY_CONSUMPTION_REFRESH_IN_MINUTES
        ): cv.positive_int,
        vol.Required(
            CONFIG_MAIN_LIVE_GAS_CONSUMPTION_REFRESH_IN_MINUTES,
            default=CONFIG_DEFAULT_LIVE_GAS_CONSUMPTION_REFRESH_IN_MINUTES
        ): cv.positive_int,
    }

    if include_account_id:
        schema = {vol.Required(CONFIG_ACCOUNT_ID): str, **schema}

    return vol.Schema(schema)


async def __async_validate_credentials__(email: str, password: str, account_id: str):
    """
    Attempt to authenticate and fetch the account.
    Returns a dict of errors (empty if successful).
    """
    errors = {}

    if not email:
        errors[CONFIG_MAIN_EMAIL] = "email_required"
        return errors

    if not password:
        errors[CONFIG_MAIN_PASSWORD] = "password_required"
        return errors

    if not account_id:
        errors[CONFIG_ACCOUNT_ID] = "account_id_required"
        return errors

    try:
        client = EDFEnergyApiClient(email, password)
        account = await client.async_get_account(account_id)
        await client.async_close()

        if account is None:
            errors[CONFIG_ACCOUNT_ID] = "account_not_found"

    except AuthenticationException:
        errors[CONFIG_MAIN_PASSWORD] = "invalid_credentials"
    except Exception as e:
        _LOGGER.error(f"Unexpected error validating EDF credentials: {e}")
        errors["base"] = "unknown"

    return errors


class EDFEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for EDF Energy integration."""

    VERSION = CONFIG_VERSION

    async def async_step_user(self, user_input):
        """Handle the initial setup step shown when user adds the integration."""
        errors = {}

        if user_input is not None:
            errors = await __async_validate_credentials__(
                user_input.get(CONFIG_MAIN_EMAIL),
                user_input.get(CONFIG_MAIN_PASSWORD),
                user_input.get(CONFIG_ACCOUNT_ID),
            )

            if len(errors) == 0:
                # Set a unique ID based on account number so you can't add the same account twice
                await self.async_set_unique_id(user_input[CONFIG_ACCOUNT_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONFIG_ACCOUNT_ID].upper(),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                __setup_account_schema__(),
                user_input if user_input is not None else {},
            ),
            errors=errors,
            description_placeholders={
                "edf_account_url": "https://www.edfenergy.com/for-homes/my-account",
            },
        )

    async def async_step_reconfigure(self, user_input):
        """Handle reconfiguration — allows updating email/password without removing the integration."""
        config = dict()
        config.update(self._get_reconfigure_entry().data)

        errors = {}

        if user_input is not None:
            config.update(user_input)

            errors = await __async_validate_credentials__(
                config.get(CONFIG_MAIN_EMAIL),
                config.get(CONFIG_MAIN_PASSWORD),
                config.get(CONFIG_ACCOUNT_ID),
            )

            if len(errors) == 0:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=config,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                # Don't show account_id on reconfigure — it can't change
                __setup_account_schema__(include_account_id=False),
                config,
            ),
            errors=errors,
            description_placeholders={
                "edf_account_url": "https://www.edfenergy.com/for-homes/my-account",
            },
        )
