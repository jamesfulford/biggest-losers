import time
import os
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import requests

from src.cache import read_json_cache, write_json_cache

FINNHUB_API_KEY = os.environ["FINNHUB_API_KEY"]


MARKET_TIMEZONE = ZoneInfo("America/New_York")


# TODO: replace with Polygon API for more accurate data
# TODO: then, pay for "Stocks Starter" to remove ratelimit
def get_candles(symbol: str, resolution: str, start: date, end: date, skip_cache=False):
    """
    Fetches candles from Finnhub.io for `symbol` with `resolution`-sized candles (1 = 1m candles, 5 = 5m candles, D = daily, etc.)
    from `start` date to `end` date, including both days. (if both are same day, it fetches for that day)
    Returns None if there is no data for the given time range.
    API docs: https://finnhub.io/docs/api/stock-candles
    Intra-day candles are unadjusted, daily candles are adjusted.
    """

    assert start > (
        date.today() - timedelta(days=365)
    ), "start must be under a 1 year ago (finnhub free tier)"

    # finnhub.io says intraday candles are unadjusted (cacheable), but not daily candles
    # do not cache candles in the future, since that list will change
    should_cache = not (end >= date.today()) and _is_intraday(resolution)
    if skip_cache:
        should_cache = False

    cache_key = "candles_{}_{}_{}_{}".format(
        symbol, resolution, start.isoformat(), end.isoformat()
    )

    if should_cache:
        cached = read_json_cache(cache_key)
        if cached:
            return _convert_candles_format(cached, resolution)

    print(
        f"fetching resolution={resolution} candles for {symbol} from {start} to {end}"
    )
    data = _get_candles(symbol, resolution, start, end)

    if should_cache:
        write_json_cache(cache_key, data)

    return _convert_candles_format(data, resolution)


def _get_candles(symbol: str, resolution: str, start: date, end: date):
    assert start <= end, "start must come before end"
    from_param = datetime.combine(start, datetime.min.time()).timestamp()
    to_param = datetime.combine(end, datetime.max.time()).timestamp()
    response = requests.get(
        "https://finnhub.io/api/v1/stock/candle",
        params={
            "symbol": symbol,
            "resolution": resolution,
            "from": int(from_param),
            "to": int(to_param),
        },
        headers={"X-Finnhub-Token": FINNHUB_API_KEY},
    )

    if response.status_code == 429:
        print("Got 429, rate limiting, waiting 10s before retrying")
        time.sleep(10)
        return _get_candles(symbol, resolution, start, end)

    response.raise_for_status()
    return response.json()


def _is_intraday(resolution: str):
    resolutions = ["1", "5", "15", "30", "60", "D", "W", "M"]
    return resolutions.index(resolution) < resolutions.index("D")


def _convert_candles_format(response_json, resolution):
    try:
        return _convert_candles_format_logic(response_json, resolution)
    except KeyError:
        return None


def _convert_candles_format_logic(response_json, resolution):
    """
    Converting finnhub format to more useful format: array of candle dictionaries
    """
    candles = []

    should_interpret_timezones = _is_intraday(resolution)
    for i in range(len(response_json["t"])):
        candle = {
            "open": response_json["o"][i],
            "high": response_json["h"][i],
            "low": response_json["l"][i],
            "close": response_json["c"][i],
            "volume": response_json["v"][i],
            "t": response_json["t"][i],
        }
        if should_interpret_timezones:
            # time at the *open* of the candle. Close is however long after `resolution` was
            candle["datetime"] = datetime.fromtimestamp(
                response_json["t"][i]
            ).astimezone(MARKET_TIMEZONE)
        else:
            candle["date"] = datetime.fromtimestamp(response_json["t"][i]).date()
        candles.append(candle)

    return candles


#
# Utilities for other scripts
#


def extract_intraday_candle_at_or_after_time(candles: list, t: datetime):
    """
    Returns the candle at the given time, or None if there is no candle at that time
    """
    for candle in candles:
        candle_t = candle["datetime"]

        if candle_t >= t:
            return candle

    return None
