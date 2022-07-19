from src.data.polygon import polygon
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from src import trading_day

from src.caching.basics import read_json_cache, write_json_cache
from src.data.types.candles import Candle

MARKET_TIMEZONE = ZoneInfo("America/New_York")


def main():
    candles = get_candles('AAPL', '1', date(2022, 1, 1), date(2022, 6, 14))
    print(len(candles), candles[0]['datetime'], candles[-1]['datetime'])


def get_candles(
    symbol: str,
    resolution: str,
    start: date,
    end: date,
    adjusted=True,
) -> list[Candle]:
    """
    Fetches candles from Polygon for `symbol` with `resolution`-sized candles (1 = 1m candles, 5 = 5m candles, D = daily, etc.)
    from `start` date to `end` date, including both days. (if both are same day, it fetches for that day)
    Returns None if there is no data for the given time range.

    NOTE: we will cache adjusted candles, make sure not to compare with unadjusted or differently adjusted values.
    """
    # TODO: use aggregation to improve cache hits, just store 1m and D candles.

    results_by_day = {}
    for day in trading_day.generate_trading_days(start, end):
        # do not cache candles for today or in the future, since that list will change
        should_cache = not (day >= date.today())

        if should_cache:
            cache_key = f"polygon/candles/{symbol}_{resolution}_{day.isoformat()}"
            cached = read_json_cache(cache_key)
            results_by_day[day] = cached

    def _build_results(results_by_day):
        candles = []
        for day in trading_day.generate_trading_days(start, end):
            day_candles = _convert_candles_format(
                results_by_day[day], resolution)
            if day_candles:
                candles.extend(day_candles)
        return candles

    # full cache hit
    if all(v for v in results_by_day.values()):
        return _build_results(results_by_day)

    fetch_start = min(k for k, v in results_by_day.items() if not v)
    fetch_end = max(k for k, v in results_by_day.items() if not v)
    logging.info(
        f"fetching resolution={resolution} candles for {symbol} from {fetch_start} to {fetch_end}"
    )

    raw_candles = _get_candles(symbol, resolution, fetch_start,
                               fetch_end, adjusted=adjusted)

    for day in trading_day.generate_trading_days(fetch_start, fetch_end):
        should_cache = not (day >= date.today())
        if not should_cache or results_by_day[day]:
            continue
        day_dt_start = datetime.combine(
            day, datetime.min.time(), tzinfo=MARKET_TIMEZONE)
        day_dt_end = day_dt_start + timedelta(days=1)
        raw_candle_results = [c for c in raw_candles
                              if c["t"] // 1000 >= day_dt_start.timestamp() and c["t"] // 1000 < day_dt_end.timestamp()]
        day_data = {'status': 'OK', 'results': raw_candle_results}
        results_by_day[day] = day_data
        write_json_cache(
            f"polygon/candles/{symbol}_{resolution}_{day.isoformat()}", day_data)

    return _build_results(results_by_day)


def _get_candles(symbol: str, resolution: str, start: date, end: date, adjusted=True):
    assert start <= end, "start must come before end"

    multiplier, timespan = _get_multiplier_and_timespan(resolution)

    limit = 50000  # max is 50k, but can reduce to test pagination logic

    # get all candles in start-end span
    # limited to N candles per request. If we get back exactly N candles, very likely need to request again with later date.
    raw_candles = []
    times = set()

    current_start = start
    while True:
        response = polygon._get_polygon(
            f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{current_start}/{end}",
            params={
                "adjusted": "true" if adjusted else "false",
                "sort": "asc",  # list will be from oldest to newest
                'limit': limit,
            },
        )

        # if response is empty (holidays, etc.), then return with everything we've collected so far (if anything)
        response_json = response.json()
        if 'results' not in response_json:
            break

        results = response_json['results']
        # when moving current_start forward, there's overlap. The `times` set is how we de-duplicate this.
        raw_candles.extend([r for r in results if r['t'] not in times])

        if len(results) < limit:  # we got all the candles we need, exit early
            break

        times.update(r['t'] for r in results)
        current_start = datetime.fromtimestamp(
            results[-1]['t'] // 1000, tz=MARKET_TIMEZONE).date()

    return raw_candles


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
