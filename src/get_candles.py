import time
import os
from datetime import datetime, date
from zoneinfo import ZoneInfo

import requests

from src.cache import read_json_cache, write_json_cache

API_KEY = os.environ["POLYGON_API_KEY"]


MARKET_TIMEZONE = ZoneInfo("America/New_York")


def get_candles(
    symbol: str,
    resolution: str,
    start: date,
    end: date,
    skip_cache=False,
    adjusted=True,
):
    """
    Fetches candles from Polygon for `symbol` with `resolution`-sized candles (1 = 1m candles, 5 = 5m candles, D = daily, etc.)
    from `start` date to `end` date, including both days. (if both are same day, it fetches for that day)
    Returns None if there is no data for the given time range.

    NOTE: we will cache adjusted candles, make sure not to compare with unadjusted or differently adjusted values.
    """

    # do not cache candles in the future, since that list will change
    should_cache = not (end >= date.today())
    if skip_cache:
        should_cache = False

    cache_key = "polygon_candles_{}_{}_{}_{}".format(
        symbol, resolution, start.isoformat(), end.isoformat()
    )

    if should_cache:
        cached = read_json_cache(cache_key)
        if cached:
            return _convert_candles_format(cached, resolution)

    print(
        f"fetching resolution={resolution} candles for {symbol} from {start} to {end}"
    )
    data = _get_candles(symbol, resolution, start, end, adjusted=adjusted)

    if should_cache:
        write_json_cache(cache_key, data)

    return _convert_candles_format(data, resolution)


def _get_candles(symbol: str, resolution: str, start: date, end: date, adjusted=True):
    assert start <= end, "start must come before end"

    multiplier, timespan = _get_multiplier_and_timespan(resolution)
    response = requests.get(
        f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start}/{end}",
        params={
            "adjusted": "true" if adjusted else "false",
            "sort": "asc",  # list will be from oldest to newest
        },
        headers={"Authorization": f"Bearer {API_KEY}"},
    )

    if response.status_code == 429:
        print("Got 429, rate limiting, waiting 10s before retrying")
        time.sleep(10)
        return _get_candles(symbol, resolution, start, end, adjusted=adjusted)

    response.raise_for_status()
    return response.json()


def _get_multiplier_and_timespan(resolution: str) -> tuple:
    return {
        "1": (1, "minute"),
        "5": (5, "minute"),
        "15": (15, "minute"),
        "30": (30, "minute"),
        "60": (1, "hour"),
        "D": (1, "day"),
        "W": (1, "week"),
        "M": (1, "month"),
    }[resolution]


def _is_intraday(resolution: str) -> bool:
    _mult, timespan = _get_multiplier_and_timespan(resolution)
    return timespan == "minute" or timespan == "hour"


def _convert_candles_format(response_json, resolution):
    if "results" not in response_json:
        return None

    return _convert_candles_format_logic(response_json, resolution)


def _convert_candles_format_logic(response_json, resolution):
    candles = []

    should_interpret_timezones = _is_intraday(resolution)
    for raw_candle in response_json["results"]:
        seconds = int(raw_candle["t"] / 1000)
        candle = {
            "open": raw_candle["o"],
            "high": raw_candle["h"],
            "low": raw_candle["l"],
            "close": raw_candle["c"],
            "volume": raw_candle["v"],
            # extra
            "trades": raw_candle.get("n", 0),
            "vwap": raw_candle.get("vw", None),
            #
            "t": seconds,
        }
        if should_interpret_timezones:
            candle["datetime"] = datetime.fromtimestamp(seconds).astimezone(
                MARKET_TIMEZONE
            )
        else:
            candle["date"] = datetime.fromtimestamp(seconds).date()

        candles.append(candle)

    return candles


#
# Utilities for other scripts
#


def extract_intraday_candle_at_or_after_time(candles: list, t: datetime, *args):
    """
    Returns the candle at the given time, or None if there is no candle at that time
    """
    for candle in candles:
        candle_t = candle["datetime"]

        if candle_t >= t:
            return candle

    return None
