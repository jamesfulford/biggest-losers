import os
from datetime import date, datetime
import time
import requests
from functools import lru_cache

from src.cache import delete_json_cache, read_json_cache, write_json_cache
from src.trading_day import previous_trading_day


API_KEY = os.environ['POLYGON_API_KEY']
HOME = os.environ['HOME']


@lru_cache(maxsize=30)
def fetch_grouped_aggs_with_cache(day, bust_cache=False):

    strftime = day.strftime("%Y-%m-%d")

    # cache intraday values separately
    key = f"grouped_aggs_{strftime}"
    # TODO: .intraday handle timezones
    if day == date.today() and datetime.now().hour < 16:
        key = f"grouped_aggs_{strftime}.intraday"

    if bust_cache:
        delete_json_cache(key)

    cached = read_json_cache(key)
    if cached:
        return cached

    data = fetch_grouped_aggs(day)

    write_json_cache(key, data)
    return data


def fetch_grouped_aggs(day):
    strftime = day.strftime("%Y-%m-%d")
    print(f'fetching grouped aggs for {strftime}')

    while True:
        response = requests.get(
            f'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{strftime}?adjusted=true&apiKey={API_KEY}')
        if response.status_code == 429:
            print("Rate limit exceeded, waiting...")
            time.sleep(10)
            continue
        response.raise_for_status()

        data = response.json()
        return data


def enrich_grouped_aggs(grouped_aggs):
    grouped_aggs['tickermap'] = {}
    for ticker in grouped_aggs['results']:
        grouped_aggs['tickermap'][ticker['T']] = ticker
    return grouped_aggs


@lru_cache(maxsize=30)
def get_last_trading_day_grouped_aggs(today):
    yesterday = previous_trading_day(today)
    yesterday_raw_grouped_aggs = fetch_grouped_aggs_with_cache(yesterday)
    while 'results' not in yesterday_raw_grouped_aggs:
        yesterday = previous_trading_day(yesterday)
        yesterday_raw_grouped_aggs = fetch_grouped_aggs_with_cache(yesterday)

    return enrich_grouped_aggs(yesterday_raw_grouped_aggs)


@lru_cache(maxsize=130)
def get_today_grouped_aggs(today, bust_cache=False):
    today_raw_grouped_aggs = fetch_grouped_aggs_with_cache(
        today, bust_cache=bust_cache)

    # skip days where API returns no data (like trading holiday)
    if 'results' not in today_raw_grouped_aggs:
        return None

    today_grouped_aggs = enrich_grouped_aggs(today_raw_grouped_aggs)
    return today_grouped_aggs


def get_last_n_candles(today, ticker, n=14):
    """
    returns last n candles for a given ticker, with entry [0] being the most recent.
    if returned None, indicates that the ticker was not trading one of those days.
    """
    candles = []
    while len(candles) < n:
        grouped_aggs = get_today_grouped_aggs(today)
        if not grouped_aggs:
            today = previous_trading_day(today)
            continue
        if ticker not in grouped_aggs['tickermap']:
            return None
        candle = grouped_aggs["tickermap"][ticker]
        candles.append(candle)
        today = previous_trading_day(today)
    return list(candles)


def get_last_2_candles(today, ticker):
    candle, candle_yesterday = tuple(
        get_last_n_candles(today, ticker, n=2))

    return candle, candle_yesterday


def get_spy_change(today):
    spy_candle, spy_candle_yesterday = get_last_2_candles(today, 'SPY')
    return (spy_candle["c"] - spy_candle_yesterday["c"]) / spy_candle_yesterday["c"]
