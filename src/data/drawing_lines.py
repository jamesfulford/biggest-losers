from datetime import datetime, timedelta
from pprint import pprint
from typing import Optional, Tuple
from src.data.aggregate_candles import aggregate_intraday_candles, filter_candles_during_market_hours
from src.data.finnhub.finnhub import CandleIntraday, get_candles
from src.trading_day import today


def find_lines(candles: list[CandleIntraday], ignore_first_candle: Optional[bool] = False) -> Tuple[list[Tuple[datetime, float]], list[Tuple[datetime, float]]]:
    """
    Returns two lists: high lines and low lines. Each line is a datetime and a price.
    Lines are sorted so they are moving outward from the last candle.
        i.e. the last high line is higher than the first high line.
        i.e. the last low line is lower than the first low line.

    The last candle's high and low are always included first in the lines.
    """
    high_lines = [(candles[-1]['datetime'], candles[-1]['high'])]
    low_lines = [(candles[-1]['datetime'], candles[-1]['low'])]

    n_2_candle = candles[-1]
    n_1_candle = candles[-2]
    # TODO: stop ignoring last 2 and always counting the last 1
    for candle in reversed(candles[:-2]):
        high_is_ascending = n_1_candle['high'] > high_lines[-1][1]
        high_is_local_high = candle['high'] < n_1_candle['high'] and n_1_candle['high'] > n_2_candle['high']
        high_line = (n_1_candle['datetime'], n_1_candle['high'])

        if high_is_ascending and high_is_local_high:
            high_lines.append(high_line)

        low_is_descending = n_1_candle['low'] < low_lines[-1][1]
        low_is_local_low = candle['low'] > n_1_candle['low'] and n_1_candle['low'] < n_2_candle['low']
        low_line = (n_1_candle['datetime'], n_1_candle['low'])

        if low_is_descending and low_is_local_low:
            low_lines.append(low_line)

        n_2_candle = n_1_candle
        n_1_candle = candle

    if not ignore_first_candle:
        # note: the first candle is not evaluated above (notice the off-by-1 evaluation) so need to add it here
        if candles[0]['low'] < low_lines[-1][1]:
            low_lines.append((candles[0]['datetime'], candles[0]['low']))

        if candles[0]['high'] > high_lines[-1][1]:
            high_lines.append((candles[0]['datetime'], candles[0]['high']))

    return high_lines, low_lines


def main():
    candles_1m = get_candles("AAPL", "1", today() - timedelta(days=0), today())
    if not candles_1m:
        print("No candles for 1m")
        return
    candles_1m = filter_candles_during_market_hours(candles_1m)
    # print(min(c['datetime'] for c in candles_1m),
    #       max(c['datetime'] for c in candles_1m))

    candles_5m = aggregate_intraday_candles(candles_1m, minute_candles=5)
    # pprint(min(candles_5m, key=lambda c: c['low']))
    # pprint(max(candles_5m, key=lambda c: c['high']))

    high_lines, low_lines = find_lines(candles_5m)
    for line in high_lines:
        print(line)
    print()
    for line in low_lines:
        print(line)

    # print(len(candles_5m[:-5]))
