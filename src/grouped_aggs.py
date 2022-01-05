import os
from datetime import date, datetime
import time
from zoneinfo import ZoneInfo
import requests
from functools import lru_cache

from src.cache import clear_json_cache, get_entry_time, get_matching_entries, read_json_cache, write_json_cache
from src.trading_day import generate_trading_days, next_trading_day, previous_trading_day


API_KEY = os.environ['POLYGON_API_KEY']
HOME = os.environ['HOME']


def get_grouped_aggs_cache_key(day: date):
    return f'grouped_aggs_{day.strftime("%Y-%m-%d")}'


#
# Cache usage:
# - for RUN, skip cache.
# - for BACKTEST, if cache is not complete, clear it all and re-fill it.
#
# Cache design:
# - always contains days M-F, but "results" are not present if holiday.
#

def _cache_is_missing_days(start: date, end: date):
    day = start
    while day <= end:
        if not read_json_cache(get_grouped_aggs_cache_key(day)):
            return True
        day = next_trading_day(day)
    return False


def _should_skip_clearing_cache(start: date, end: date):
    # if partial cache is more recent than last close, we can continue
    try:
        # weekends -> monday, otherwise no-op
        start_trading_day = next_trading_day(previous_trading_day(start))
        last_cache_refresh_started_time = get_entry_time(
            get_grouped_aggs_cache_key(start_trading_day)).astimezone(ZoneInfo("America/New_York"))

        now = datetime.now().astimezone(ZoneInfo("America/New_York"))
        today_or_prev_trading_day = previous_trading_day(
            next_trading_day(now.date()))
        today_or_prev_close = datetime(today_or_prev_trading_day.year, today_or_prev_trading_day.month,
                                       today_or_prev_trading_day.day, 16, 0, 0).replace(tzinfo=ZoneInfo("America/New_York"))

        if last_cache_refresh_started_time > today_or_prev_close:
            return True
    except:
        # cache entry we are checking for is missing, so we should definitely act as if clear
        return False

    return False


def _refetch_cache(start: date, end: date):
    day = start
    while day <= end:
        fetch_grouped_aggs_with_cache(day)
        day = next_trading_day(day)


def get_current_cache_range():
    entries = get_matching_entries("grouped_aggs_")
    if not entries or len(entries) < 2:
        return None
    entries.sort()

    start_entry, end_entry = entries[0], entries[-1]
    return datetime.strptime(start_entry, 'grouped_aggs_%Y-%m-%d').date(), datetime.strptime(end_entry, 'grouped_aggs_%Y-%m-%d').date()


def get_cache_prepared_date_range_with_leadup_days(days: int):
    assert days >= 0
    cache_range = get_current_cache_range()
    assert cache_range, "cache must be prepared"
    cache_start, cache_end = cache_range

    # need at least 100 trading days for 100 EMA to compute
    backtestable_range = list(
        generate_trading_days(cache_start, cache_end))[days:]
    start, end = backtestable_range[0], backtestable_range[-1]
    return start, end


def prepare_cache_grouped_aggs(start: date, end: date) -> None:
    if _cache_is_missing_days(start, end):
        if not _should_skip_clearing_cache(start, end):
            print("cache is not complete and must be cleared")
            clear_json_cache("grouped_aggs_")
        else:
            print("cache is not complete, but we can continue building it")

        _refetch_cache(start, end)
    else:
        print("cache is all present, will not refetch")


@lru_cache(maxsize=30)
def fetch_grouped_aggs_with_cache(day: date, skip_cache=False):
    should_cache = day != date.today()
    if skip_cache:
        should_cache = False

    cache_key = get_grouped_aggs_cache_key(day)

    if should_cache:
        cached = read_json_cache(cache_key)
        if cached:
            return cached

    data = fetch_grouped_aggs(day)

    if should_cache:
        write_json_cache(cache_key, data)

    return data


def fetch_grouped_aggs(day: date):
    strftime = day.strftime("%Y-%m-%d")
    print(f'fetching grouped aggs for {strftime}')

    while True:
        # TODO: adjusted=false, do the adjustments on our side (more cache hits)
        response = requests.get(
            f'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{strftime}?adjusted=true&apiKey={API_KEY}')
        if response.status_code == 429:
            print("Rate limit exceeded, waiting...")
            time.sleep(10)
            continue
        response.raise_for_status()

        data = response.json()
        return data


def _enrich_grouped_aggs(grouped_aggs):
    grouped_aggs['tickermap'] = {}
    for ticker in grouped_aggs['results']:
        grouped_aggs['tickermap'][ticker['T']] = ticker
    return grouped_aggs

#
# Utilities for strategies to use
#


@lru_cache(maxsize=30)
def get_last_trading_day_grouped_aggs(today: date):
    yesterday = previous_trading_day(today)
    yesterday_raw_grouped_aggs = fetch_grouped_aggs_with_cache(yesterday)
    while 'results' not in yesterday_raw_grouped_aggs:
        yesterday = previous_trading_day(yesterday)
        yesterday_raw_grouped_aggs = fetch_grouped_aggs_with_cache(yesterday)

    return _enrich_grouped_aggs(yesterday_raw_grouped_aggs)


@lru_cache(maxsize=130)
def get_today_grouped_aggs(today: date, skip_cache=False):
    today_raw_grouped_aggs = fetch_grouped_aggs_with_cache(
        today, skip_cache=skip_cache)

    # skip days where API returns no data (like trading holiday)
    if 'results' not in today_raw_grouped_aggs:
        return None

    today_grouped_aggs = _enrich_grouped_aggs(today_raw_grouped_aggs)
    return today_grouped_aggs


def get_last_n_candles(today: date, ticker, n=14):
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


def get_last_2_candles(today: date, ticker: str):
    candle, candle_yesterday = tuple(
        get_last_n_candles(today, ticker, n=2))

    return candle, candle_yesterday


def get_spy_change(today):
    spy_candle, spy_candle_yesterday = get_last_2_candles(today, 'SPY')
    return (spy_candle["c"] - spy_candle_yesterday["c"]) / spy_candle_yesterday["c"]
