from datetime import datetime
import json
import logging
import os
from typing import List
import requests

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
    try:
        access_token = _get_access_token()
        headers = kwargs.get("headers", {})
        headers.update({
            "Authorization": f"Bearer {_get_access_token()}",
        })
        kwargs['headers'] = headers
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

def get_fundamentals(symbols: List[str]) -> dict:
    chunks = [symbols[x:x+100] for x in range(0, len(symbols), 100)]

    fundamentals = {}
    for chunk in chunks:
        fundamentals.update(_get_fundamentals(chunk))
    return fundamentals


def _get_fundamentals(symbols: List[str]):
    """
    {
        "AAPL": {
            "fundamental": {
                "symbol": "AAPL",
                "high52": 182.94,
                "low52": 116.21,
                "dividendAmount": 0.88,
                "dividendYield": 0.54,
                "dividendDate": "2022-02-04 00:00:00.000",
                "peRatio": 27.09501,
                "pegRatio": 0.431242,
                "pbRatio": 37.07428,
                "prRatio": 7.03984,
                "pcfRatio": 23.80739,
                "grossMarginTTM": 43.01906,
                "grossMarginMRQ": 43.76377,
                "netProfitMarginTTM": 26.57914,
                "netProfitMarginMRQ": 27.93981,
                "operatingMarginTTM": 30.90032,
                "operatingMarginMRQ": 33.47291,
                "returnOnEquity": 145.5673,
                "returnOnAssets": 27.35279,
                "returnOnInvestment": 44.18407,
                "quickRatio": 0.99799,
                "currentRatio": 1.03781,
                "interestCoverage": 942.9091,
                "totalDebtToCapital": 63.06065,
                "ltDebtToEquity": 148.2358,
                "totalDebtToEquity": 170.714,
                "epsTTM": 6.02325,
                "epsChangePercentTTM": 62.83015,
                "epsChangeYear": 24.76506,
                "epsChange": 0,
                "revChangeYear": 0,
                "revChangeTTM": 28.62223,
                "revChangeIn": 48.68642,
                "sharesOutstanding": 16319441000,
                "marketCapFloat": 16308,
                "marketCap": 2663333,
                "bookValuePerShare": 0,
                "shortIntToFloat": 0,
                "shortIntDayToCover": 0,
                "divGrowthRate3Year": 0,
                "dividendPayAmount": 0.22,
                "dividendPayDate": "2022-02-10 00:00:00.000",
                "beta": 1.19054,
                "vol1DayAvg": 87065060,
                "vol10DayAvg": 87065056,
                "vol3MonthAvg": 2089220340
            },
            "cusip": "037833100",
            "symbol": "AAPL",
            "description": "Apple Inc. - Common Stock",
            "exchange": "NASDAQ",
            "assetType": "EQUITY"
        },
    """
    response = _get_data("/v1/instruments", params={
        "symbol": ",".join(symbols),
        "projection": "fundamental"
    })
    fundamentals = {}
    for symbol, r in response.json().items():
        fundamentals[symbol] = _build_fundamental(r)
    return fundamentals


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
