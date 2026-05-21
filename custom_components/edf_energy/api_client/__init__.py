import logging
import json
from typing import Any, List
import aiohttp
from asyncio import TimeoutError
from datetime import (datetime, timedelta, time, timezone)
from threading import RLock
from zoneinfo import ZoneInfo
from homeassistant.util.dt import (as_utc, now, as_local, parse_datetime, parse_date)
from ..const import INTEGRATION_VERSION

_LOGGER = logging.getLogger(__name__)

# Modified from HomeAssistant-OctopusEnergy by BottlecapDave (MIT)
# Modified by [your name] [year] — adapted for EDF Energy / Kraken API

user_agent_value = "bobby5291-ha-edf-energy"

EDF_BASE_URL = "https://api.edfgb-kraken.energy"

api_token_query = '''mutation {{
  obtainKrakenToken(input: {{ email: "{email}", password: "{password}" }}) {{
    token
    refreshToken
    refreshExpiresIn
  }}
}}'''

api_token_refresh_query = '''mutation {{
  obtainKrakenToken(input: {{ refreshToken: "{refresh_token}" }}) {{
    token
    refreshToken
    refreshExpiresIn
  }}
}}'''

extended_electricity_consumption_query = '''query ExtendedAnnualElectricityConsumption($mpan: String!) {
  extendedAnnualElectricityConsumption(mpan: $mpan) {
    eacStandard
    eacDay
    eacNight
  }
}'''

annual_gas_consumption_query = '''query AnnualGasConsumption($mprn: String!) {
  annualGasConsumption(mprn: $mprn) {
    aq
    supplierName
    supplierEffectiveFromDate
    aqEffectiveFromDate
  }
}'''

account_query = '''query {{
  account(accountNumber: "{account_id}") {{
    balance
    overdueBalance
    projectedBalance
    shouldReviewPayments
    recommendedBalanceAdjustment
    canRenewTariff

    electricityAgreements(active: true) {{
      meterPoint {{
        mpan
        direction
        meters(includeInactive: false) {{
          activeFrom
          activeTo
          serialNumber
          makeAndType
          meterType
          smartImportElectricityMeter {{
            deviceId
            manufacturer
            model
            firmwareVersion
          }}
          smartExportElectricityMeter {{
            deviceId
            manufacturer
            model
            firmwareVersion
          }}
        }}
        agreements(includeInactive: false) {{
          validFrom
          validTo
          tariff {{
            ... on TariffType {{
              productCode
              tariffCode
              displayName
            }}
            ... on HalfHourlyTariff {{
              productCode
              tariffCode
              displayName
            }}
            ... on DayNightTariff {{
              productCode
              tariffCode
              displayName
            }}
            ... on FourRateEvTariff {{
              productCode
              tariffCode
              displayName
            }}
            ... on PrepayTariff {{
              productCode
              tariffCode
              displayName
            }}
          }}
        }}
      }}
    }}

    gasAgreements(active: true) {{
      meterPoint {{
        mprn
        meters(includeInactive: false) {{
          activeFrom
          activeTo
          serialNumber
          consumptionUnits
          modelName
          mechanism
          smartGasMeter {{
            deviceId
            manufacturer
            model
            firmwareVersion
          }}
        }}
        agreements(includeInactive: false) {{
          validFrom
          validTo
          tariff {{
            ... on TariffType {{
              tariffCode
              productCode
            }}
          }}
        }}
      }}
    }}
  }}
}}'''

live_consumption_query = '''query SmartMeterTelemetry(
  $deviceId: String!,
  $start: DateTime,
  $end: DateTime,
  $grouping: TelemetryGrouping
) {
  smartMeterTelemetry(
    deviceId: $deviceId,
    start: $start,
    end: $end,
    grouping: $grouping
  ) {
    readAt
    consumption
    export
    demand
    consumptionDelta
    costDelta
    costDeltaWithTax
  }
}'''



integration_context_header = "Ha-Integration-Context"


def get_valid_from(rate):
  return rate["valid_from"]

def get_start(rate):
  return (rate["start"].timestamp(), rate["start"].fold)

def rates_to_thirty_minute_increments(data, period_from: datetime, period_to: datetime, tariff_code: str, price_cap: float = None):
  """Process the collection of rates to ensure they're in 30 minute periods"""
  starting_period_from = period_from
  results = []
  if ("results" in data):
    items = data["results"]
    items.sort(key=get_valid_from)

    for item in items:
      value_inc_vat = float(item["value_inc_vat"])

      is_capped = False
      if (price_cap is not None and value_inc_vat > price_cap):
        value_inc_vat = price_cap
        is_capped = True

      if "valid_from" in item and item["valid_from"] is not None:
        valid_from = as_utc(parse_datetime(item["valid_from"]))
        if (valid_from < starting_period_from):
          valid_from = starting_period_from
      else:
        valid_from = starting_period_from

      if "valid_to" in item and item["valid_to"] is not None:
        target_date = as_utc(parse_datetime(item["valid_to"]))
        if (target_date > period_to):
          target_date = period_to
      else:
        target_date = period_to

      while valid_from < target_date:
        valid_to = valid_from + timedelta(minutes=30)
        results.append({
          "value_inc_vat": value_inc_vat,
          "start": valid_from,
          "end": valid_to,
          "tariff_code": tariff_code,
          "is_capped": is_capped
        })
        valid_from = valid_to
        starting_period_from = valid_to

  return results

def get_standing_charge(data: list, tariff_code: str):
  for item in data:
    return {
      "start": parse_datetime(item["valid_from"]) if "valid_from" in item and item["valid_from"] is not None else None,
      "end": parse_datetime(item["valid_to"]) if "valid_to" in item and item["valid_to"] is not None else None,
      "value_inc_vat": float(item["value_inc_vat"]),
      "tariff_code": tariff_code,
    }
  return None


class ApiException(Exception): ...

class ServerException(ApiException): ...

class TimeoutException(ApiException): ...

class RequestException(ApiException):
  errors: list[str]

  def __init__(self, message: str, errors: list[str]):
    super().__init__(message)
    self.errors = errors

class AuthenticationException(RequestException): ...


def process_graphql_response(data: Any, url: str, request_context: str, ignore_errors: bool, accepted_error_codes: list[str]):
  if ("graphql" in url and "errors" in data and ignore_errors == False):
    msg = f'Errors in request ({url}) ({request_context}): {data["errors"]}'
    errors = list(map(lambda error: error["message"].strip(".,!"), data["errors"]))
    errors_as_string = ', '.join(errors)
    _LOGGER.warning(msg)

    for error in data["errors"]:
      if ("extensions" in error and
          "errorCode" in error["extensions"] and
          error["extensions"]["errorCode"] in ("KT-CT-1139", "KT-CT-1111", "KT-CT-1143", "KT-CT-1134", "KT-CT-1135")):
        raise AuthenticationException(f"Authentication failed - {errors_as_string}. See logs for more details.", errors)

      if ("extensions" in error and
          "errorCode" in error["extensions"] and
          error["extensions"]["errorCode"] in accepted_error_codes):
        return None

    raise RequestException(f"Failed - {errors_as_string}. See logs for more details.", errors)

  return data


class EDFEnergyApiClient:
  _refresh_token_lock = RLock()
  _session_lock = RLock()

  def __init__(self, email: str, password: str, timeout_in_seconds = 20):
    if email is None:
      raise Exception('Email is not set')
    if password is None:
      raise Exception('Password is not set')

    self._email = email
    self._password = password
    self._base_url = EDF_BASE_URL

    self._graphql_token = None
    self._graphql_expiration = None
    self._graphql_refresh_token = None
    self._graphql_refresh_expiration = None

    self._timeout = aiohttp.ClientTimeout(total=None, sock_connect=timeout_in_seconds, sock_read=timeout_in_seconds)
    self._default_headers = { "user-agent": f'{user_agent_value}/{INTEGRATION_VERSION}' }

    self._session = None

  async def async_close(self):
    with self._session_lock:
      if self._session is not None:
        await self._session.close()

  def _create_client_session(self):
    if self._session is not None:
      return self._session

    with self._session_lock:
      if self._session is not None:
        return self._session

      self._session = aiohttp.ClientSession(headers=self._default_headers, skip_auto_headers=['User-Agent'])
      return self._session

  async def async_refresh_token(self):
    """Refresh user token"""
    if (self._graphql_expiration is not None and (self._graphql_expiration - timedelta(minutes=5)) > now()):
      return

    with self._refresh_token_lock:
      if (self._graphql_expiration is not None and (self._graphql_expiration - timedelta(minutes=5)) > now()):
        return

      if (self._graphql_refresh_expiration is not None and self._graphql_refresh_expiration >= now()):
        _LOGGER.debug("Refresh token expired - clearing")
        self._graphql_refresh_token = None
        self._graphql_expiration = None

      try:
        try:
          await self.__async_fetch_token()
        except AuthenticationException:
          if (self._graphql_refresh_token is not None):
            _LOGGER.debug("Failed to refresh auth token using refresh token, attempting to use original credentials")
            self._graphql_refresh_token = None
            self._graphql_expiration = None
            await self.__async_fetch_token()
          else:
            raise

      except TimeoutError:
        _LOGGER.warning(f'Failed to connect. Timeout of {self._timeout} exceeded.')
        raise TimeoutException()

  async def __async_fetch_token(self):
    client = self._create_client_session()
    url = f'{self._base_url}/v1/graphql/'
    payload = {
      "query": api_token_query.format(email=self._email, password=self._password)
        if self._graphql_refresh_token is None
        else api_token_refresh_query.format(refresh_token=self._graphql_refresh_token)
    }
    headers = { "context": "refresh-token" }
    async with client.post(url, headers=headers, json=payload) as token_response:
      token_response_body = await self.__async_read_response__(token_response, url)
      if (token_response_body is not None and
          "data" in token_response_body and
          "obtainKrakenToken" in token_response_body["data"] and
          token_response_body["data"]["obtainKrakenToken"] is not None and
          "token" in token_response_body["data"]["obtainKrakenToken"] and
          "refreshToken" in token_response_body["data"]["obtainKrakenToken"] and
          "refreshExpiresIn" in token_response_body["data"]["obtainKrakenToken"]):

        self._graphql_token = token_response_body["data"]["obtainKrakenToken"]["token"]
        self._graphql_refresh_token = token_response_body["data"]["obtainKrakenToken"]["refreshToken"]
        self._graphql_refresh_expiration = datetime.fromtimestamp(token_response_body["data"]["obtainKrakenToken"]["refreshExpiresIn"], tz=timezone.utc)
        self._graphql_expiration = now() + timedelta(hours=1)
      elif (self._graphql_expiration is None or self._graphql_expiration > now()):
        raise AuthenticationException("Failed to retrieve auth token and current token is expired", [])
      else:
        _LOGGER.error("Failed to retrieve auth token")

  def map_electricity_meters(self, meter_point):
    is_export = (meter_point["meterPoint"]["direction"] == 'EXPORT') \
      if "meterPoint" in meter_point and "direction" in meter_point["meterPoint"] and meter_point["meterPoint"]["direction"] is not None \
      else None

    meters = list(
      map(lambda m: {
        "active_from": parse_date(m["activeFrom"]) if m["activeFrom"] is not None else None,
        "active_to": parse_date(m["activeTo"]) if m["activeTo"] is not None else None,
        "serial_number": m["serialNumber"],
        "is_export": is_export if is_export is not None else m["smartExportElectricityMeter"] is not None,
        "is_smart_meter": f'{m["meterType"]}'.startswith("S1") or f'{m["meterType"]}'.startswith("S2"),
        "device_id": m["smartImportElectricityMeter"]["deviceId"] if m["smartImportElectricityMeter"] is not None else None,
        "manufacturer": m["smartImportElectricityMeter"]["manufacturer"]
          if m["smartImportElectricityMeter"] is not None
          else m["smartExportElectricityMeter"]["manufacturer"]
          if m["smartExportElectricityMeter"] is not None
          else m["makeAndType"],
        "model": m["smartImportElectricityMeter"]["model"]
          if m["smartImportElectricityMeter"] is not None
          else m["smartExportElectricityMeter"]["model"]
          if m["smartExportElectricityMeter"] is not None
          else None,
        "firmware": m["smartImportElectricityMeter"]["firmwareVersion"]
          if m["smartImportElectricityMeter"] is not None
          else m["smartExportElectricityMeter"]["firmwareVersion"]
          if m["smartExportElectricityMeter"] is not None
          else None
      },
      meter_point["meterPoint"]["meters"]
        if "meterPoint" in meter_point and "meters" in meter_point["meterPoint"] and meter_point["meterPoint"]["meters"] is not None
        else []
      )
    )

    meters.sort(key=lambda meter: meter["active_from"], reverse=True)

    return {
      "mpan": meter_point["meterPoint"]["mpan"],
      "meters": meters,
      "agreements": list(map(lambda a: {
        "start": a["validFrom"],
        "end": a["validTo"],
        "tariff_code": a["tariff"]["tariffCode"] if "tariff" in a and "tariffCode" in a["tariff"] else None,
        "product_code": a["tariff"]["productCode"] if "tariff" in a and "productCode" in a["tariff"] else None,
        "display_name": a["tariff"]["displayName"] if "tariff" in a and "displayName" in a["tariff"] else None,
      },
      meter_point["meterPoint"]["agreements"]
        if "meterPoint" in meter_point and "agreements" in meter_point["meterPoint"] and meter_point["meterPoint"]["agreements"] is not None
        else []
      ))
    }

  def map_gas_meters(self, meter_point):
    meters = list(
      map(lambda m: {
        "active_from": parse_date(m["activeFrom"]) if m["activeFrom"] is not None else None,
        "active_to": parse_date(m["activeTo"]) if m["activeTo"] is not None else None,
        "serial_number": m["serialNumber"],
        "consumption_units": m["consumptionUnits"],
        "is_smart_meter": m["mechanism"] == "S1" or m["mechanism"] == "S2",
        "device_id": m["smartGasMeter"]["deviceId"] if m["smartGasMeter"] is not None else None,
        "manufacturer": m["smartGasMeter"]["manufacturer"] if m["smartGasMeter"] is not None else m["modelName"],
        "model": m["smartGasMeter"]["model"] if m["smartGasMeter"] is not None else None,
        "firmware": m["smartGasMeter"]["firmwareVersion"] if m["smartGasMeter"] is not None else None
      },
      meter_point["meterPoint"]["meters"]
        if "meterPoint" in meter_point and "meters" in meter_point["meterPoint"] and meter_point["meterPoint"]["meters"] is not None
        else []
      )
    )

    meters.sort(key=lambda meter: meter["active_from"], reverse=True)

    return {
      "mprn": meter_point["meterPoint"]["mprn"],
      "meters": meters,
      "agreements": list(map(lambda a: {
        "start": a["validFrom"],
        "end": a["validTo"],
        "tariff_code": a["tariff"]["tariffCode"] if "tariff" in a and "tariffCode" in a["tariff"] else None,
        "product_code": a["tariff"]["productCode"] if "tariff" in a and "productCode" in a["tariff"] else None,
      },
      meter_point["meterPoint"]["agreements"]
        if "meterPoint" in meter_point and "agreements" in meter_point["meterPoint"] and meter_point["meterPoint"]["agreements"] is not None
        else []
      ))
    }

  async def async_get_account(self, account_id: str):
    """Get the user's account"""
    await self.async_refresh_token()

    try:
      client = self._create_client_session()
      url = f'{self._base_url}/v1/graphql/'
      payload = { "query": account_query.format(account_id=account_id) }
      headers = { "Authorization": self._graphql_token, "context": "get-account" }
      async with client.post(url, json=payload, headers=headers) as account_response:
        account_response_body = await self.__async_read_response__(account_response, url)
        _LOGGER.debug(f'account: {account_response_body}')

        if (account_response_body is not None and
            "data" in account_response_body and
            "account" in account_response_body["data"] and
            account_response_body["data"]["account"] is not None):

          account = account_response_body["data"]["account"]

          return {
            "id": account_id,
            "balance": account.get("balance"),
            "overdue_balance": account.get("overdueBalance"),
            "projected_balance": account.get("projectedBalance"),
            "should_review_payments": account.get("shouldReviewPayments"),
            "recommended_balance_adjustment": account.get("recommendedBalanceAdjustment"),
            "can_renew_tariff": account.get("canRenewTariff"),
            "electricity_meter_points": list(map(self.map_electricity_meters,
              account["electricityAgreements"]
                if "electricityAgreements" in account and account["electricityAgreements"] is not None
                else []
            )),
            "gas_meter_points": list(map(self.map_gas_meters,
              account["gasAgreements"]
                if "gasAgreements" in account and account["gasAgreements"] is not None
                else []
            )),
          }
        else:
          _LOGGER.error("Failed to retrieve account")

    except TimeoutError:
      _LOGGER.warning(f'Failed to connect. Timeout of {self._timeout} exceeded.')
      raise TimeoutException()

    return None

  async def async_get_extended_electricity_consumption(self, mpan: str):
    """Get extended annual electricity consumption estimates (EAC) for an MPAN."""
    await self.async_refresh_token()
    try:
      client = self._create_client_session()
      url = f'{self._base_url}/v1/graphql/'
      payload = {
        "query": extended_electricity_consumption_query,
        "variables": {"mpan": mpan},
      }
      headers = {"Authorization": self._graphql_token, "context": "extended-electricity-consumption"}
      async with client.post(url, json=payload, headers=headers) as response:
        body = await self.__async_read_response__(response, url)
        if (body is not None and
            "data" in body and
            "extendedAnnualElectricityConsumption" in body["data"] and
            body["data"]["extendedAnnualElectricityConsumption"] is not None):
          data = body["data"]["extendedAnnualElectricityConsumption"]
          return {
            "eac_standard": float(data["eacStandard"]) if data.get("eacStandard") is not None else None,
            "eac_day": float(data["eacDay"]) if data.get("eacDay") is not None else None,
            "eac_night": float(data["eacNight"]) if data.get("eacNight") is not None else None,
          }
    except TimeoutError:
      _LOGGER.warning(f'Failed to connect. Timeout of {self._timeout} exceeded.')
      raise TimeoutException()
    return None

  async def async_get_annual_gas_consumption(self, mprn: str):
    """Get annual gas consumption (AQ) for an MPRN."""
    await self.async_refresh_token()
    try:
      client = self._create_client_session()
      url = f'{self._base_url}/v1/graphql/'
      payload = {
        "query": annual_gas_consumption_query,
        "variables": {"mprn": mprn},
      }
      headers = {"Authorization": self._graphql_token, "context": "annual-gas-consumption"}
      async with client.post(url, json=payload, headers=headers) as response:
        body = await self.__async_read_response__(response, url)
        if (body is not None and
            "data" in body and
            "annualGasConsumption" in body["data"] and
            body["data"]["annualGasConsumption"] is not None):
          data = body["data"]["annualGasConsumption"]
          return {
            "aq": float(data["aq"]) if data.get("aq") is not None else None,
            "supplier_name": data.get("supplierName"),
            "supplier_effective_from": data.get("supplierEffectiveFromDate"),
            "aq_effective_from": data.get("aqEffectiveFromDate"),
          }
    except TimeoutError:
      _LOGGER.warning(f'Failed to connect. Timeout of {self._timeout} exceeded.')
      raise TimeoutException()
    return None

  async def async_get_smart_meter_consumption(self, device_id: str, period_from: datetime, period_to: datetime):
    """Get the user's smart meter consumption"""
    await self.async_refresh_token()

    try:
      client = self._create_client_session()
      url = f'{self._base_url}/v1/graphql/'
      payload = {
        "query": live_consumption_query,
        "variables": {
          "deviceId": device_id,
          "start": period_from.isoformat(),
          "end": period_to.isoformat(),
          "grouping": "HALF_HOURLY"
        }
      }
      headers = { "Authorization": self._graphql_token, "context": "smart-meter-consumption" }
      async with client.post(url, json=payload, headers=headers) as response:
        response_body = await self.__async_read_response__(response, url)

        if (response_body is not None and
            "data" in response_body and
            "smartMeterTelemetry" in response_body["data"] and
            response_body["data"]["smartMeterTelemetry"] is not None and
            len(response_body["data"]["smartMeterTelemetry"]) > 0):
          return list(map(lambda mp: {
            "total_consumption": float(mp["consumption"]) / 1000 if mp.get("consumption") is not None else None,
            "total_export": float(mp["export"]) / 1000 if mp.get("export") is not None else None,
            "consumption": float(mp["consumptionDelta"]) / 1000 if mp.get("consumptionDelta") is not None else 0,
            "demand": float(mp["demand"]) if mp.get("demand") is not None else None,
            "cost_delta": float(mp["costDelta"]) if mp.get("costDelta") is not None else None,
            "cost_delta_with_tax": float(mp["costDeltaWithTax"]) if mp.get("costDeltaWithTax") is not None else None,
            "start": parse_datetime(mp["readAt"]),
            "end": parse_datetime(mp["readAt"]) + timedelta(minutes=30)
          }, response_body["data"]["smartMeterTelemetry"]))
        else:
          _LOGGER.debug(f"Failed to retrieve smart meter consumption - device_id: {device_id}; period_from: {period_from}; period_to: {period_to}")

    except TimeoutError:
      _LOGGER.warning(f'Failed to connect. Timeout of {self._timeout} exceeded.')
      raise TimeoutException()

    return None

  async def __async_fetch_electricity_rates_endpoint(self, client, product_code: str, tariff_code: str, endpoint: str, period_from: datetime, period_to: datetime):
    """Fetch all pages from a single electricity rates endpoint. Returns list or None on failure."""
    results = []
    page = 1
    has_more = True
    period_from_str = period_from.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    period_to_str = period_to.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {"Authorization": self._graphql_token, "context": "electricity-rates"}

    while has_more:
      url = f'{self._base_url}/v1/products/{product_code}/electricity-tariffs/{tariff_code}/{endpoint}?period_from={period_from_str}&period_to={period_to_str}&page={page}'
      try:
        async with client.get(url, headers=headers) as response:
          data = await self.__async_read_response__(response, url)
          if data is None:
            return None
          results = results + rates_to_thirty_minute_increments(data, period_from, period_to, tariff_code)
          has_more = "next" in data and data["next"] is not None
          if has_more:
            page += 1
      except RequestException:
        return None

    return results

  async def async_get_electricity_rates(self, product_code: str, tariff_code: str, period_from: datetime, period_to: datetime):
    """Get electricity rates, handling single-rate and day/night tariffs."""
    try:
      client = self._create_client_session()

      # Try standard (single-rate) endpoint first
      results = await self.__async_fetch_electricity_rates_endpoint(
        client, product_code, tariff_code, "standard-unit-rates", period_from, period_to
      )

      if results is None:
        # Tariff has day/night rates — fetch both and combine
        _LOGGER.debug(f'Standard rates unavailable for {tariff_code}, trying day/night endpoints')
        day_results = await self.__async_fetch_electricity_rates_endpoint(
          client, product_code, tariff_code, "day-unit-rates", period_from, period_to
        ) or []
        night_results = await self.__async_fetch_electricity_rates_endpoint(
          client, product_code, tariff_code, "night-unit-rates", period_from, period_to
        ) or []
        results = day_results + night_results
        if not results:
          return None

    except TimeoutError:
      _LOGGER.warning(f'Failed to connect. Timeout of {self._timeout} exceeded.')
      raise TimeoutException()

    results.sort(key=get_start)
    return results

  async def async_get_electricity_standing_charge(self, product_code: str, tariff_code: str, period_from: datetime, period_to: datetime):
    """Get the electricity standing charge"""
    try:
      client = self._create_client_session()
      url = f'{self._base_url}/v1/products/{product_code}/electricity-tariffs/{tariff_code}/standing-charges?period_from={period_from.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}&period_to={period_to.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}'
      headers = { "Authorization": self._graphql_token, "context": "electricity-standing-charge" }
      async with client.get(url, headers=headers) as response:
        data = await self.__async_read_response__(response, url)
        if (data is not None and "results" in data and len(data["results"]) > 0):
          return get_standing_charge(data["results"], tariff_code)

    except TimeoutError:
      _LOGGER.warning(f'Failed to connect. Timeout of {self._timeout} exceeded.')
      raise TimeoutException()

    return None

  async def async_get_electricity_consumption(self, mpan: str, serial_number: str, period_from: datetime = None, period_to: datetime = None, page_size: int = None):
    """Get the electricity consumption"""
    try:
      client = self._create_client_session()

      query_params = []
      if period_from is not None:
        query_params.append(f'period_from={period_from.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}')
      if period_to is not None:
        query_params.append(f'period_to={period_to.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}')
      if page_size is not None:
        query_params.append(f'page_size={page_size}')

      query_string = '&'.join(query_params)
      url = f"{self._base_url}/v1/electricity-meter-points/{mpan}/meters/{serial_number}/consumption{f'?{query_string}' if query_string else ''}"
      headers = { "Authorization": self._graphql_token, "context": "electricity-consumption" }
      async with client.get(url, headers=headers) as response:
        data = await self.__async_read_response__(response, url)
        if (data is not None and "results" in data):
          results = []
          for item in data["results"]:
            item = self.__process_consumption(item)
            if (period_from is None or as_utc(item["start"]) >= period_from) and (period_to is None or as_utc(item["end"]) <= period_to):
              results.append(item)
            else:
              _LOGGER.debug(f'Skipping electricity consumption item outside requested scope - mpan: {mpan}')
          results.sort(key=self.__get_interval_end)
          return results

    except TimeoutError:
      _LOGGER.warning(f'Failed to connect. Timeout of {self._timeout} exceeded.')
      raise TimeoutException()

    return None

  async def async_get_gas_rates(self, product_code: str, tariff_code: str, period_from: datetime, period_to: datetime):
    """Get the gas rates"""
    try:
      client = self._create_client_session()
      url = f'{self._base_url}/v1/products/{product_code}/gas-tariffs/{tariff_code}/standard-unit-rates?period_from={period_from.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}&period_to={period_to.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}'
      headers = { "Authorization": self._graphql_token, "context": "gas-rates" }
      async with client.get(url, headers=headers) as response:
        data = await self.__async_read_response__(response, url)
        if data is None:
          return None
        return rates_to_thirty_minute_increments(data, period_from, period_to, tariff_code)

    except TimeoutError:
      _LOGGER.warning(f'Failed to connect. Timeout of {self._timeout} exceeded.')
      raise TimeoutException()

  async def async_get_gas_standing_charge(self, product_code: str, tariff_code: str, period_from: datetime, period_to: datetime):
    """Get the gas standing charge"""
    try:
      client = self._create_client_session()
      url = f'{self._base_url}/v1/products/{product_code}/gas-tariffs/{tariff_code}/standing-charges?period_from={period_from.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}&period_to={period_to.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}'
      headers = { "Authorization": self._graphql_token, "context": "gas-standing-charge" }
      async with client.get(url, headers=headers) as response:
        data = await self.__async_read_response__(response, url)
        if (data is not None and "results" in data and len(data["results"]) > 0):
          return get_standing_charge(data["results"], tariff_code)

    except TimeoutError:
      _LOGGER.warning(f'Failed to connect. Timeout of {self._timeout} exceeded.')
      raise TimeoutException()

    return None

  async def async_get_gas_consumption(self, mprn: str, serial_number: str, period_from: datetime = None, period_to: datetime = None, page_size: int = None):
    """Get the gas consumption"""
    try:
      client = self._create_client_session()

      query_params = []
      if period_from is not None:
        query_params.append(f'period_from={period_from.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}')
      if period_to is not None:
        query_params.append(f'period_to={period_to.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}')
      if page_size is not None:
        query_params.append(f'page_size={page_size}')

      query_string = '&'.join(query_params)
      url = f"{self._base_url}/v1/gas-meter-points/{mprn}/meters/{serial_number}/consumption{f'?{query_string}' if query_string else ''}"
      headers = { "Authorization": self._graphql_token, "context": "gas-consumption" }
      async with client.get(url, headers=headers) as response:
        data = await self.__async_read_response__(response, url)
        if (data is not None and "results" in data):
          results = []
          for item in data["results"]:
            item = self.__process_consumption(item)
            if (period_from is None or as_utc(item["start"]) >= period_from) and (period_to is None or as_utc(item["end"]) <= period_to):
              results.append(item)
            else:
              _LOGGER.debug(f'Skipping gas consumption item outside requested scope - mprn: {mprn}')
          results.sort(key=self.__get_interval_end)
          return results

    except TimeoutError:
      _LOGGER.warning(f'Failed to connect. Timeout of {self._timeout} exceeded.')
      raise TimeoutException()

    return None

  def __get_interval_end(self, item):
    return (item["end"].timestamp(), item["end"].fold)

  def __process_consumption(self, item):
    return {
      "consumption": float(item["consumption"]),
      "start": as_utc(parse_datetime(item["interval_start"])),
      "end": as_utc(parse_datetime(item["interval_end"]))
    }

  async def __async_read_response__(self, response, url, ignore_errors=False, accepted_error_codes=[]):
    """Reads the response, logging any errors"""
    text = await response.text()

    if response.status >= 400:
      if response.status >= 500:
        msg = f'Response received - {url} - EDF Energy server error: {response.status}; {text}'
        _LOGGER.warning(msg)
        raise ServerException(msg)
      elif response.status in [401, 403]:
        msg = f'Response received - {url} - Unauthenticated request: {response.status}; {text}'
        _LOGGER.warning(msg)
        raise AuthenticationException(msg, [])
      elif response.status not in [404]:
        msg = f'Response received - {url} - Failed to send request: {response.status}; {text}'
        _LOGGER.warning(msg)
        raise RequestException(msg, [])

      _LOGGER.info(f"Response received - {url} - Unexpected response: {response.status}; {text}")
      return None

    _LOGGER.debug(f'Response received - {url} - Successful response')

    data_as_json = None
    try:
      data_as_json = json.loads(text)
    except:
      raise Exception(f'Failed to extract response json: {url}; {text}')

    return process_graphql_response(data_as_json, url, "edf-energy", ignore_errors, accepted_error_codes)
