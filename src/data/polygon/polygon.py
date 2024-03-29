from datetime import date, timedelta
from functools import lru_cache
import logging
import os
import random
from typing import Iterable, Optional

import requests
from src.caching.basics import read_json_cache, write_json_cache

from src.trading_day import now, today, today_or_previous_trading_day
from src.wait import wait_until


def get_polygon_api_key():
    return os.environ["POLYGON_API_KEY"]


# TODO: refactor grouped_aggs to use these helpers
def _get_polygon(url: str, **kwargs):
    while True:
        response = requests.get(
            url, **kwargs, headers={"Authorization": f"Bearer {get_polygon_api_key()}"})
        if response.status_code == 429:
            right_now = now()

            target_time = right_now.replace(
                # some jitter to resolve multi-process sharing/hogging of quota
                second=random.randint(0, 10), microsecond=0) + timedelta(minutes=1)
            logging.info(
                f"Rate limit exceeded, {url.replace('https://api.polygon.io', '')}, waiting for {target_time - right_now}...")
            wait_until(target_time)
            continue

        response.raise_for_status()

        return response


def _get_polygon_with_next_url_pagination(url: str, **initial_kwargs):
    response = _get_polygon(url, **initial_kwargs).json()

    for result in response["results"]:
        yield result

    # recursive generators, be careful
    if "next_url" in response:
        for result in _get_polygon_with_next_url_pagination(response["next_url"]):
            yield result


#
# Tickers
#
@lru_cache(maxsize=40)
def get_tickers_by_type(t: str, day: date):
    # assuming will not change intraday, would hate to rebuild this cache every time
    should_cache = day <= today()
    cache_key = f"polygon/ticker_details/{t}_{day}"

    if should_cache:
        cached = read_json_cache(cache_key)
        if cached:
            return _format_tickers_by_type_response(cached)

    logging.info(f"Fetching tickers with type={t} active on {day}")
    data = _get_tickers_by_type_raw(t, day)

    if should_cache:
        write_json_cache(cache_key, data)

    return _format_tickers_by_type_response(data)


def _format_tickers_by_type_response(tickers: list):
    symbol_to_ticker_map = {}
    for ticker in tickers:
        """{
            "ticker": "AAL",
            "name": "American Airlines Group Inc.",
            "market": "stocks",
            "locale": "us",
            "primary_exchange": "XNAS",
            "type": "CS",
            "active": true,
            "currency_name": "usd",
            "cik": "0000006201",
            "composite_figi": "BBG005P7Q881",
            "share_class_figi": "BBG005P7Q907",
            "last_updated_utc": "2022-01-14T00:00:00Z"
        }"""
        symbol_to_ticker_map[ticker["ticker"]] = ticker
    return symbol_to_ticker_map


def _get_tickers_by_type_raw(t: str, day: date) -> list:
    return list(_get_polygon_with_next_url_pagination(
        f"https://api.polygon.io/v3/reference/tickers",
        params={
            "type": t,
            "market": "stocks",
            "active": "true",
            "sort": "ticker",
            "order": "asc",
            "limit": "1000",
            "date": day.isoformat(),
        },
    ))

#
# Ticker utilities
#


def is_ticker_type(ticker: str, t: str, day: Optional[date] = None):
    if not day:
        day = today()

    day = today_or_previous_trading_day(day)

    return ticker in get_tickers_by_type(t, day=day)


def is_ticker_one_of(ticker: str, types: Iterable[str], day: Optional[date] = None):
    if not day:
        logging.warning("WARNING: 'day' not provided to `is_ticker_one_of`")
    return any((
        is_ticker_type(ticker, stock_type, day=day)
        for stock_type in types
    ))
