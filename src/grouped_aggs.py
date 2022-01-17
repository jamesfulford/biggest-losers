import os
from datetime import date, datetime
import time
from zoneinfo import ZoneInfo
import requests
from functools import lru_cache

from src.cache import (
    clear_json_cache,
    get_entry_time,
    get_matching_entries,
    read_json_cache,
    write_json_cache,
)
from src.trading_day import (
    generate_trading_days,
    get_last_market_close,
    get_last_market_open,
    get_market_close_on_day,
    get_market_open_on_day,
    is_during_market_hours,
    next_trading_day,
    now,
    previous_trading_day,
    today_or_next_trading_day,
    today_or_previous_trading_day,
)


API_KEY = os.environ["POLYGON_API_KEY"]


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


def get_cache_entry_refresh_time(day: date) -> datetime:
    return now(get_entry_time(get_grouped_aggs_cache_key(day)))


def _should_skip_clearing_cache(start: date, end: date):
    # if partial cache is more recent than last close, we can continue
    try:
        last_cache_refresh_started_time = get_cache_entry_refresh_time(
            today_or_next_trading_day(start)
        )

        market_now = now()

        # if last cache refresh was during market hours, should clear
        if is_during_market_hours(last_cache_refresh_started_time):
            return False

        # if right now is during market hours, should clear
        if is_during_market_hours(market_now):
            return False

        # so, it's outside market hours and last cache refresh was outside market hours.

        # if both are after the same session, then we can continue with existing cache
        return get_last_market_close(
            last_cache_refresh_started_time
        ) == get_last_market_close(market_now)
    except:
        # cache entry we are checking for is missing, so we should definitely act as if clear
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
    return (
        datetime.strptime(start_entry, "grouped_aggs_%Y-%m-%d").date(),
        datetime.strptime(end_entry, "grouped_aggs_%Y-%m-%d").date(),
    )


def get_cache_prepared_date_range_with_leadup_days(days: int):
    assert days >= 0
    cache_range = get_current_cache_range()
    assert cache_range, "cache must be prepared"
    cache_start, cache_end = cache_range

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
    print(f"fetching grouped aggs for {strftime}")

    while True:
        # TODO: adjusted=false, do the adjustments on our side (more cache hits)
        response = requests.get(
            f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{strftime}",
            params={
                "adjusted": "true",
            },
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        if response.status_code == 429:
            print("Rate limit exceeded, waiting...")
            time.sleep(10)
            continue
        response.raise_for_status()

        data = response.json()
        return data


def _enrich_grouped_aggs(grouped_aggs):
    grouped_aggs["tickermap"] = {}
    for ticker in grouped_aggs["results"]:
        grouped_aggs["tickermap"][ticker["T"]] = ticker
    return grouped_aggs


#
# Utilities for strategies to use
#


@lru_cache(maxsize=30)
def get_last_trading_day_grouped_aggs(today: date):
    yesterday = previous_trading_day(today)
    yesterday_raw_grouped_aggs = fetch_grouped_aggs_with_cache(yesterday)
    while "results" not in yesterday_raw_grouped_aggs:
        yesterday = previous_trading_day(yesterday)
        yesterday_raw_grouped_aggs = fetch_grouped_aggs_with_cache(yesterday)

    return _enrich_grouped_aggs(yesterday_raw_grouped_aggs)


@lru_cache(maxsize=130)
def get_today_grouped_aggs(today: date, skip_cache=False):
    today_raw_grouped_aggs = fetch_grouped_aggs_with_cache(
        today, skip_cache=skip_cache)

    # skip days where API returns no data (like trading holiday)
    if "results" not in today_raw_grouped_aggs:
        return None

    today_grouped_aggs = _enrich_grouped_aggs(today_raw_grouped_aggs)
    return today_grouped_aggs


@lru_cache(maxsize=130)
def get_today_grouped_aggs_from_cache(today: date):
    """
    Returns (cache_hit_bool, grouped_aggs)
    If no cache hit, grouped_aggs is None
    If cache hit and is holiday, grouped_aggs is None
    Else, grouped_aggs is the data
    """
    cache_key = get_grouped_aggs_cache_key(today)
    cache = read_json_cache(cache_key)

    if not cache:
        return False, None

    # skip days where API returns no data (like trading holiday)
    if "results" not in cache:
        return True, None
    return True, _enrich_grouped_aggs(cache)


def get_last_n_candles(today: date, ticker, n=14):
    """
    returns last n candles for a given ticker, with entry [0] being the most recent.
    if returned None, indicates:
        - the ticker was not trading one of those days (newly listed?)
        - cache does not contain enough days of data
    """
    candles = []
    while len(candles) < n:
        cache_hit, grouped_aggs = get_today_grouped_aggs_from_cache(today)
        if not cache_hit:
            # we don't have enough data in the cache
            return None

        if not grouped_aggs:
            # holiday
            today = previous_trading_day(today)
            continue

        if ticker not in grouped_aggs["tickermap"]:
            # was not trading that day (listed recently?)
            return None

        candle = grouped_aggs["tickermap"][ticker]
        candles.append(candle)
        today = previous_trading_day(today)
    return list(candles)


def get_last_2_candles(today: date, ticker: str):
    candle, candle_yesterday = tuple(get_last_n_candles(today, ticker, n=2))

    return candle, candle_yesterday


def get_spy_change(today):
    spy_candle, spy_candle_yesterday = get_last_2_candles(today, "SPY")
    return (spy_candle["c"] - spy_candle_yesterday["c"]) / spy_candle_yesterday["c"]
