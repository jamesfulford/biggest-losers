import time
import os
from datetime import datetime, date
from zoneinfo import ZoneInfo
from functools import lru_cache

import requests

FINNHUB_API_KEY = os.environ["FINNHUB_API_KEY"]


MARKET_TIMEZONE = ZoneInfo("America/New_York")


@lru_cache(maxsize=100)
def get_candles(symbol: str, resolution: str, start: date, end: date):
    """
    Fetches candles from Finnhub.io for `symbol` with `resolution`-sized candles (1 = 1m candles, 5 = 5m candles, D = daily, etc.)
    from `start` date to `end` date, including both days. (if both are same day, it fetches for that day)
    API docs: https://finnhub.io/docs/api/stock-candles
    """
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
        return get_candles(symbol, resolution, start, end)

    response_json = response.json()
    print(response_json["s"], len(response_json["t"]))
    response.raise_for_status()

    return _convert_candles_format(response_json, resolution)


def _convert_candles_format(response_json, resolution):
    """
    Converting finnhub format to more useful format: array of candle dictionaries
    """
    candles = []

    resolutions = ["1", "5", "15", "30", "60", "D", "W", "M"]
    should_interpret_timezones = resolutions.index(resolution) < resolutions.index("D")
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
