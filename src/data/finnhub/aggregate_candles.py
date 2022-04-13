from pprint import pprint
from typing import cast
from src.data.types.candles import CandleIntraday
from src.trading_day import is_during_market_hours, today


def _group_candles_by_bucket(candles: list[CandleIntraday], bucket_factor=5) -> dict[str, list[CandleIntraday]]:
    buckets = {}
    for candle in candles:
        m = candle['datetime'].replace(
            minute=candle['datetime'].minute // bucket_factor)
        if m not in buckets:
            buckets[m] = []
        buckets[m].append(candle)
    return buckets


def aggregate_intraday_candles(candles: list[CandleIntraday], minute_candles=5) -> list[CandleIntraday]:
    """
    Aggregates intraday candles into a single candle.
    """
    assert 60 % minute_candles == 0, "minute_candles must evenly divide 60"

    groups = _group_candles_by_bucket(candles, bucket_factor=minute_candles)
    aggs = cast(list[CandleIntraday], [{
        'open': group[0]['open'],
        'high': max(c['high'] for c in group),
        'low': min(c['low'] for c in group),
        'close': group[-1]['close'],
        'volume': sum(c['volume'] for c in group),
        'datetime': group[0]['datetime'],
    } for group in groups.values()])
    aggs.sort(key=lambda c: c['datetime'])
    return aggs


def filter_candles_during_market_hours(candles: list[CandleIntraday]) -> list[CandleIntraday]:
    """
    Filters out candles outside of the market hours.
    """
    return [c for c in candles if is_during_market_hours(c['datetime'])]


def main():
    from src.data.finnhub.finnhub import get_candles
    candles_1m = get_candles("AAPL", "1", today(), today())
    if not candles_1m:
        print("No candles for 1m")
        return
    # candles_1m = [c for c in candles_1m if c['datetime'].time() >= time(9, 30)]
    # candles_1m = candles_1m[:10]

    pprint(candles_1m)
    candles_1m = cast(list[CandleIntraday], candles_1m)
    aggs = aggregate_intraday_candles(candles_1m, minute_candles=5)
    print()
    pprint(aggs)
