from datetime import date, datetime
from functools import lru_cache
import json
import logging
import os
from time import sleep
from typing import List, Union
import requests
from src.cache import read_json_cache, write_json_cache

from src.pathing import get_paths


def _get_consumer_key():
    return os.environ['TD_CONSUMER_KEY']


def _get_token():
    path = get_paths()['data']["inputs"]["td-token_json"]
    with open(path) as f:
        return json.load(f)


def _get_access_token():
    return _get_token()['access_token']


def _log_response(response: requests.Response):
    logging.debug(
        f"TD: {response.status_code} {response.url} => {response.text}")


def _should_warn_about_delay(url: str):
    return not url.startswith("/v1/instruments")


def _get_data(url: str, **kwargs):
    logging.info("fetching TD fundamental data")
    try:
        access_token = _get_access_token()
        headers = kwargs.get("headers", {})
        headers.update({
            "Authorization": f"Bearer {access_token}",
        })
        kwargs['headers'] = headers
        response = requests.get(
            "https://api.tdameritrade.com" + url, **kwargs)
        if response.status_code == 429:
            logging.info("Rate limited, waiting...")
            sleep(5)
            return _get_data(url, **kwargs)
        _log_response(response)
        response.raise_for_status()
    except:
        if _should_warn_about_delay(url):
            logging.warn("TD: data will be 15m delayed")
        params = kwargs.get("params", {})
        params.update({
            "apikey": _get_consumer_key(),
        })
        kwargs['params'] = params
        response = requests.get(
            "https://api.tdameritrade.com" + url, **kwargs)
        if response.status_code == 429:
            logging.info("Rate limited, waiting...")
            sleep(5)
            return _get_data(url, **kwargs)
        _log_response(response)
        response.raise_for_status()

    return response

#
# Quotes
#


def get_quotes(symbols: List[str]):
    """
    "NRGU": {
        "52WkHigh": 356.0,
        "52WkLow": 85.89,
        "askId": "P",
        "askPrice": 339.9,
        "askSize": 300,
        "assetMainType": "EQUITY",
        "assetType": "EQUITY",
        "bidId": "P",
        "bidPrice": 327.72,
        "bidSize": 100,
        "bidTick": " ",
        "closePrice": 330.0,
        "cusip": "\",
        "delayed": false,
        "description": "MicroSectors U.S. Big Oil Index 3X Leveraged ETN",
        "digits": 2,
        "divAmount": 0.0,
        "divDate": "",
        "divYield": 0.0,
        "exchange": "p",
        "exchangeName": "PACIFIC",
        "highPrice": 356.0,
        "lastId": "P",
        "lastPrice": 337.99,
        "lastSize": 0,
        "lowPrice": 327.0,
        "marginable": true,
        "mark": 337.99,
        "markChangeInDouble": 7.99,
        "markPercentChangeInDouble": 2.4212,
        "nAV": 0.0,
        "netChange": 7.99,
        "netPercentChangeInDouble": 2.4212,
        "openPrice": 340.55,
        "peRatio": 0.0,
        "quoteTimeInLong": 1646172261975,
        "realtimeEntitled": true,
        "regularMarketLastPrice": 337.99,
        "regularMarketLastSize": 4,
        "regularMarketNetChange": 7.99,
        "regularMarketPercentChangeInDouble": 2.4212,
        "regularMarketTradeTimeInLong": 1646169000002,
        "securityStatus": "Normal",
        "shortable": true,
        "symbol": "NRGU",
        "totalVolume": 257805,
        "tradeTimeInLong": 1646172091728,
        "volatility": 0.2284
    }
    """
    response = _get_data(f"/v1/marketdata/quotes", params={
        "symbol": ",".join(symbols)
    })

    def _get_price_rounded(quote: dict, price_key: str):
        return round(quote[price_key], quote['digits'])

    quotes = {}
    for symbol, quote in response.json().items():
        quotes[symbol] = {
            "ask": _get_price_rounded(quote, 'askPrice'),
            "bid": _get_price_rounded(quote, 'bidPrice'),
            "spread": round(quote['askPrice'] - quote['bidPrice'], quote['digits']),
            "day_candle": {
                "open": _get_price_rounded(quote, 'openPrice'),
                "high": _get_price_rounded(quote, 'highPrice'),
                "low": _get_price_rounded(quote, 'lowPrice'),
                "close": _get_price_rounded(quote, 'closePrice'),
                "volume": quote['totalVolume'],
            },
        }

    return quotes


def get_quote(symbol: str) -> dict:
    return get_quotes([symbol])[symbol]


#
# Fundamentals
#

def _get_fundamentals_cache_key(symbol: str, day: date):
    return f"fundamentals_{symbol}_{day.isoformat()}"


def get_fundamentals(symbols: List[str]) -> dict:
    """
    Fetches TD fundamental data for all symbols provided. Cached based on day fetched.
    Passing `day` will cause the cache lookup to be based on that day.
    """
    day = date.today()

    fundamentals = {}

    # Check cache
    symbols_to_fetch = []
    for symbol in symbols:
        key = _get_fundamentals_cache_key(symbol, day)
        data = read_json_cache(key)
        if data:
            fundamentals[symbol] = data
        else:
            symbols_to_fetch.append(symbol)

    # Fetch in chunks
    chunks = [symbols_to_fetch[x:x+100]
              for x in range(0, len(symbols_to_fetch), 100)]
    for chunk in chunks:
        fundamentals.update(_get_fundamentals(chunk))

    # Write cache
    for symbol, data in fundamentals.items():
        key = _get_fundamentals_cache_key(symbol, day)
        write_json_cache(key, data)

    # map values
    new_fundamentals = {}
    for symbol, r in fundamentals.items():
        new_fundamentals[symbol] = _build_fundamental(r)
    return new_fundamentals


def _get_fundamentals(symbols: List[str]):
    response = _get_data("/v1/instruments", params={
        "symbol": ",".join(symbols),
        "projection": "fundamental"
    })
    return response.json()


def _build_fundamental(fundamental_response: dict) -> dict:
    fundamental = fundamental_response['fundamental']
    return {
        "shares": {
            "float": int(fundamental['marketCapFloat'] * 1000000),
            "shares_outstanding": int(fundamental['sharesOutstanding']),
        },
        "volume_averages": {
            "1_day": int(fundamental['vol1DayAvg']),
            "10_day": int(fundamental['vol10DayAvg']),
            "3_month": int(fundamental['vol3MonthAvg']),
        },
        # Seems to always be 0, maybe I need to sign short agreement?
        # "short_interest": {
        #     "to_float": fundamental["shortIntToFloat"],
        #     "day_to_cover": fundamental["shortIntDayToCover"],
        # },
        "ratios": {
            "pe_ratio": fundamental['peRatio'],
        },
        "dividends": {
            # Annual dividend amount, I don't care for now
            # "dividend_amount": fundamental['dividendAmount'],
            # "dividend_yield": fundamental['dividendYield'],

            # If you want to get the dividend, buy before this day
            "ex_date": datetime.strptime(fundamental['dividendDate'], "%Y-%m-%d %H:%M:%S.%f").date() if fundamental['dividendDate'].strip() else None,
            "amount": fundamental['dividendPayAmount'],
            "pay_date": datetime.strptime(fundamental['dividendPayDate'], "%Y-%m-%d %H:%M:%S.%f").date() if fundamental['dividendPayDate'].strip() else None,
        },
        "symbol": fundamental_response['symbol'],
        "exchange": fundamental_response['exchange'],
        # reports ETFs as equities
        "asset_type": fundamental_response['assetType'],
        "cusip": fundamental_response['cusip'],
        "description": fundamental_response['description'],
    }


def get_fundamental(symbol: str) -> dict:
    return get_fundamentals([symbol])[symbol]


def main():
    fundamentals = get_fundamentals(
        ["AAPL", "MSFT", "AMZN", "FB", "GOOG", "TSLA", "NFLX"])
    for symbol, fundamentals in fundamentals.items():
        print(symbol, fundamentals['shares']['float'])
    # # float_ratio = fundamentals['marketCapFloat'] * \
    # #     1000000 / fundamentals['sharesOutstanding']
    # from pprint import pprint
    # pprint(fundamentals)

    # pprint(fundamentals['shares']['float'])

    # float_shares_millions = fundamentals['marketCapFloat']
    # quote = get_quote("SIRI")
    # float_market_cap_millions = float_shares_millions * quote['ask']
    # print(float_market_cap_millions)
