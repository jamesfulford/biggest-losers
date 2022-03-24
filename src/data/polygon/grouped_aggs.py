from datetime import date, datetime, time
import logging
from time import sleep
from typing import Optional, Tuple, TypeVar, TypedDict, cast
import requests
from functools import lru_cache

from src.cache import (
    clear_json_cache,
    get_entry_time,
    get_matching_entries,
    read_json_cache,
    write_json_cache,
)
from src.data.polygon.polygon import get_polygon_api_key
from src.trading_day import (
    generate_trading_days,
    get_last_market_close,
    is_during_market_hours,
    next_trading_day,
    now,
    previous_trading_day,
    today,
    today_or_next_trading_day,
)


def get_grouped_aggs_cache_key(day: date) -> str:
    return f'polygon/grouped_aggs/{day.strftime("%Y-%m-%d")}'


class Ticker(TypedDict):
    T: str
    o: float
    h: float
    l: float
    c: float
    v: int  # NOTE: often is a float
    n: int
    vw: float


TickerLike = TypeVar("TickerLike", bound=Ticker)


def _build_ticker(ticker: dict) -> Ticker:
    return {
        "T": ticker["T"],
        "o": ticker["o"],
        "h": ticker["h"],
        "l": ticker["l"],
        "c": ticker["c"],
        "v": int(ticker["v"]),
        "n": int(ticker["n"]),
        "vw": ticker["vw"],
    }

#
# Cache usage:
# - for RUN, skip cache.
# - for BACKTEST, if cache is not complete, clear it all and re-fill it.
#
# Cache design:
# - always contains days M-F, but "results" are not present if holiday.
#


def _cache_is_missing_days(start: date, end: date) -> bool:
    day = start
    while day <= end:
        if not read_json_cache(get_grouped_aggs_cache_key(day)):
            return True
        day = next_trading_day(day)
    return False


def get_cache_entry_refresh_time(day: date) -> datetime:
    return now(get_entry_time(get_grouped_aggs_cache_key(day)))


def _should_skip_clearing_cache(start: date, end: date) -> bool:
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


def _refetch_cache(start: date, end: date) -> None:
    day = start
    while day <= end:
        fetch_grouped_aggs_with_cache(day)
        day = next_trading_day(day)


def get_current_cache_range() -> Optional[Tuple[date, date]]:
    entries = get_matching_entries("polygon/grouped_aggs/")
    if not entries or len(entries) < 2:
        return None
    entries.sort()

    start_entry, end_entry = entries[0], entries[-1]
    return (
        datetime.strptime(start_entry, "polygon/grouped_aggs/%Y-%m-%d").date(),
        datetime.strptime(end_entry, "polygon/grouped_aggs/%Y-%m-%d").date(),
    )


def get_cache_prepared_date_range_with_leadup_days(days: int) -> Tuple[date, date]:
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
            logging.warning("cache is not complete and must be cleared")
            clear_json_cache("polygon/grouped_aggs/")
        else:
            logging.info(
                "cache is not complete, but we can continue building it")

        _refetch_cache(start, end)
    else:
        logging.info("cache is all present, will not refetch")


class GroupedAggsResponse(TypedDict):
    results: list[Ticker]


class EnrichedGroupedAggsResponse(GroupedAggsResponse):
    tickermap: dict[str, Ticker]


def fetch_grouped_aggs_with_cache(day: date) -> GroupedAggsResponse:
    should_cache = True
    if day == today():
        # if after close, allow caching, otherwise don't
        should_cache = now().time() > time(16, 0)

    cache_key = get_grouped_aggs_cache_key(day)

    if should_cache:
        cached = read_json_cache(cache_key)
        if cached:
            return cached

    data = fetch_grouped_aggs(day)

    if should_cache:
        write_json_cache(cache_key, data)

    return data


def fetch_grouped_aggs(day: date) -> GroupedAggsResponse:
    strftime = day.strftime("%Y-%m-%d")
    logging.info(f"fetching grouped aggs for {strftime}")

    while True:
        # TODO: adjusted=false, do the adjustments on our side (more cache hits)
        response = requests.get(
            f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{strftime}",
            params={
                "adjusted": "true",
            },
            headers={"Authorization": f"Bearer {get_polygon_api_key()}"},
        )
        if response.status_code == 429:
            logging.info("Rate limit exceeded, waiting...")
            sleep(10)
            continue
        response.raise_for_status()

        data = response.json()
        return data


def _enrich_grouped_aggs(grouped_aggs: GroupedAggsResponse) -> EnrichedGroupedAggsResponse:
    enriched_grouped_aggs = cast(EnrichedGroupedAggsResponse, grouped_aggs)
    enriched_grouped_aggs["tickermap"] = {}
    for ticker in enriched_grouped_aggs["results"]:
        enriched_grouped_aggs["tickermap"][ticker["T"]] = ticker
    return enriched_grouped_aggs


#
# Utilities for strategies to use
#


def get_today_grouped_aggs(today: date) -> Optional[EnrichedGroupedAggsResponse]:
    today_raw_grouped_aggs = fetch_grouped_aggs_with_cache(today)

    # skip days where API returns no data (like trading holiday)
    if "results" not in today_raw_grouped_aggs:
        return None

    today_grouped_aggs = _enrich_grouped_aggs(today_raw_grouped_aggs)
    return today_grouped_aggs


@lru_cache(maxsize=130)
def get_today_grouped_aggs_from_cache(today: date) -> Tuple[bool, Optional[EnrichedGroupedAggsResponse]]:
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


def get_last_n_candles(today: date, ticker: str, n: int = 14) -> Optional[list[Ticker]]:
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


def get_last_2_candles(today: date, ticker: str) -> Optional[Tuple[Ticker, Ticker]]:
    last_2_candles = get_last_n_candles(today, ticker, n=2)
    if not last_2_candles:
        return None
    candle, candle_yesterday = tuple(last_2_candles)
    return candle, candle_yesterday


def get_spy_change(today) -> Optional[float]:
    last_2_candles = get_last_2_candles(today, "SPY")
    if not last_2_candles:
        return None
    spy_candle, spy_candle_yesterday = tuple(last_2_candles)
    return (spy_candle["c"] - spy_candle_yesterday["c"]) / spy_candle_yesterday["c"]


def main():
    print(get_last_n_candles(date(2021, 12, 1), "SPY", n=6))
    print("allo")
