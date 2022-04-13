import logging
import time
import os
from datetime import datetime, date, timedelta
from typing import Optional, TypedDict, Union, cast
from zoneinfo import ZoneInfo

import requests

from src.caching.basics import read_json_cache, write_json_cache
from src.data.types.candles import CandleInterday, CandleIntraday

FINNHUB_API_KEY = os.environ["FINNHUB_API_KEY"]


MARKET_TIMEZONE = ZoneInfo("America/New_York")


def get_1m_candles(symbol: str, start: date, end: date) -> Optional[list[CandleIntraday]]:
    candles_1m = get_candles(symbol, "1", start, end)
    if candles_1m is None:
        return None
    return cast(list[CandleIntraday], candles_1m)


def get_d_candles(symbol: str, start: date, end: date) -> Optional[list[CandleInterday]]:
    candles_d = get_candles(symbol, "D", start, end)
    if candles_d is None:
        return None
    return cast(list[CandleInterday], candles_d)


def get_candles(symbol: str, resolution: str, start: date, end: date) -> Optional[list[Union[CandleInterday, CandleIntraday]]]:
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
    # do not cache candles for today or in the future, since that list will change
    should_cache = not (end >= date.today()) and _is_intraday(resolution)

    # TODO: hit cache if is subset of another cache entry (e.g. 1m candles on April 2 is included in 1m candles from April 1 to April 8)
    cache_key = f"finnhub/candles/{symbol}_{resolution}_{start.isoformat()}_{end.isoformat()}"

    if should_cache:
        cached = read_json_cache(cache_key)
        if cached:
            return _convert_candles_format(cached, resolution)

    logging.info(
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
        logging.info("Got 429, rate limiting, waiting 10s before retrying")
        time.sleep(10)
        return _get_candles(symbol, resolution, start, end)

    response.raise_for_status()
    return response.json()


def _is_intraday(resolution: str):
    resolutions = ["1", "5", "15", "30", "60", "D", "W", "M"]
    return resolutions.index(resolution) < resolutions.index("D")


def _convert_candles_format(response_json, resolution) -> Optional[list[Union[CandleInterday, CandleIntraday]]]:
    try:
        return _convert_candles_format_logic(response_json, resolution)
    except KeyError:
        logging.warning(
            f"Finnhub get_candles response format was unexpected: {response_json}")
        return None


def _convert_candles_format_logic(response_json, resolution) -> list[Union[CandleInterday, CandleIntraday]]:
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
            "volume": int(response_json["v"][i]),
        }
        if should_interpret_timezones:
            # time at the *open* of the candle. Close is however long after `resolution` was
            candle["datetime"] = datetime.fromtimestamp(
                response_json["t"][i]
            ).astimezone(MARKET_TIMEZONE)
        else:
            candle["date"] = datetime.fromtimestamp(
                response_json["t"][i]).date()
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
