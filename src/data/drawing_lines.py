from datetime import date, datetime, timedelta
from pprint import pprint
from typing import Iterable, Optional, Tuple, TypeVar, TypedDict, Union
from src.data.aggregate_candles import aggregate_intraday_candles, filter_candles_during_market_hours
from src.data.finnhub.finnhub import Candle, CandleInterday, CandleIntraday, get_1m_candles, get_candles, get_d_candles
from src.trading_day import previous_trading_day, today


class Line(TypedDict):
    time: Union[date, datetime]
    value: float
    source: str
    state: str


T = TypeVar("T")


def pair_indices_with_values(values: list[T], indices: list[int]) -> list[Tuple[T, int]]:
    return [(values[i], i) for i in indices]


def yield_rising_highs(values: list):
    max_value = values[0]

    if max_value > values[1]:
        yield max_value

    for value in values[1:]:
        if value >= max_value:
            max_value = value
            yield max_value


def find_local_maximas(values: list[float]) -> list[int]:
    """
    Returns list of indices where values are at local highs.
    Includes ends as local maxima.
    In case of ties, prefers the rightmost index.
    """
    local_maximas = []
    first, second = values[0], values[1]
    if first > second:
        local_maximas.append(0)

    for i in range(1, len(values) - 1):
        before, current, after = values[i - 1], values[i], values[i + 1]
        if current >= before and current > after:
            local_maximas.append(i)

    last, second_to_last = values[-1], values[-2]
    if last >= second_to_last:
        local_maximas.append(len(values) - 1)

    return local_maximas


CandleLike = TypeVar('CandleLike', bound=Candle)


def find_lines(candles: list[CandleLike]) -> Tuple[list[Tuple[Union[datetime, date], float]], list[Tuple[Union[datetime, date], float]]]:
    """
    Returns two lists: high lines and low lines. Each line is a datetime and a price.
    Lines are sorted so they are moving outward from the last candle.
        i.e. the last high line is higher than the first high line.
        i.e. the last low line is lower than the first low line.
    """

    highs = [c['high'] for c in candles]
    local_maxima_with_index = pair_indices_with_values(
        highs, find_local_maximas(highs))
    rising_highs = list(yield_rising_highs(
        list(reversed(local_maxima_with_index))))
    rising_high_candles = [candles[i] for _, i in rising_highs]
    high_lines = [(c.get('datetime', c.get('date')), c['high'])
                  for c in rising_high_candles]

    negative_lows = [-c['low'] for c in candles]
    local_maxima_with_index = pair_indices_with_values(
        negative_lows, find_local_maximas(negative_lows))
    declining_lows_with_negated_values = list(yield_rising_highs(
        list(reversed(local_maxima_with_index))))
    declining_low_candles = [candles[i]
                             for _, i in declining_lows_with_negated_values]
    low_lines = [(c.get('datetime', c.get('date')), c['low'])
                 for c in declining_low_candles]

    return high_lines, low_lines


def remove_duplicate_lines(lines: Iterable[Line]) -> Iterable[Line]:
    values_already_seen = set()
    for line in lines:
        value = line['value']
        if value not in values_already_seen:
            values_already_seen.add(value)
            yield line


def find_james_lines(symbol: str, day: Optional[date] = None, ignore_last_n_5m_candles: int = 5) -> Optional[list[Line]]:
    this_day = today() if day is None else day
    # Use 1m candles and aggregate to 5m so we get more cache hits in backtests (no other code uses 5m)
    candles_1m = get_1m_candles(symbol, this_day -
                                timedelta(days=7), this_day)
    if not candles_1m:
        return None
    candles_1m = filter_candles_during_market_hours(candles_1m)
    # TODO: candles_1m are unadjusted candles, need to detect if is an issue
    candles_5m = aggregate_intraday_candles(candles_1m, minute_candles=5)
    candles_5m = candles_5m[:-ignore_last_n_5m_candles]

    candles_d = get_d_candles(symbol, today() -
                              timedelta(days=180), today())
    if not candles_d:
        return None

    return extract_james_lines(candles_intraday=candles_5m, candles_d=candles_d)


def extract_james_lines(*, candles_intraday: list[CandleIntraday], candles_d: list[CandleInterday]) -> list[Line]:
    """
    Given intraday candles from last few days and interday candles from last few months,
    returns a list of lines to watch for crossings of.
    """
    # Pure function, so we can do backtests
    this_day = candles_intraday[-1]['datetime'].date()

    # Today 5m lines
    today_candles_intraday = [
        c for c in candles_intraday if c['datetime'].date() == this_day]
    high_lines_today_intraday, low_lines_today_intraday = find_lines(
        today_candles_intraday)
    high_lines_today_intraday = [Line(
        time=t[0], value=t[1], source="today-high", state='active') for t in high_lines_today_intraday]
    low_lines_today_intraday = [Line(
        time=t[0], value=t[1], source="today-low", state='active') for t in low_lines_today_intraday]

    # Recent lines
    before_today_candles_intraday = [
        c for c in candles_intraday if c['datetime'].date() < this_day]
    high_lines_before_today_intraday, low_lines_before_today_intraday = find_lines(
        before_today_candles_intraday)
    high_lines_before_today_intraday = [Line(
        time=t[0], value=t[1], source="recent-high", state='active') for t in high_lines_before_today_intraday]
    low_lines_before_today_intraday = [Line(
        time=t[0], value=t[1], source="recent-low", state='active') for t in low_lines_before_today_intraday]

    # Daily lines
    high_lines_d, low_lines_d = find_lines(candles_d)
    high_lines_d = [Line(time=t[0], value=t[1], source="daily-high",
                         state='active') for t in high_lines_d]
    low_lines_d = [Line(time=t[0], value=t[1], source="daily-low",
                        state='active') for t in low_lines_d]

    past_high_lines = list(remove_duplicate_lines(
        high_lines_before_today_intraday + high_lines_d))
    past_low_lines = list(remove_duplicate_lines(
        low_lines_before_today_intraday + low_lines_d))

    today_high, today_low = high_lines_today_intraday[-1]['value'], low_lines_today_intraday[-1]['value']

    for line in past_high_lines:
        if line['value'] <= today_high:
            line['state'] = 'inactive'
    for line in past_low_lines:
        if line['value'] >= today_low:
            line['state'] = 'inactive'

    return sorted(past_low_lines + low_lines_today_intraday + past_high_lines + high_lines_today_intraday, key=lambda x: x['value'], reverse=True)


def main():
    lines = find_james_lines("AAPL")
    if not lines:
        return
    for line in lines:
        print(f"{line['value']:<8.2f} {line['source']:<12} {line['state']:<8}")

    # print("=" * 80)
    # for line in low_lines:
    #     print(f"{line['value']:<8.2f} {line['source']:<12} {line['state']:<8}")

    # print(find_local_maximas(
    #     list(([0, 1, 3, 3, 4, 5, 6, 7, 8, 9, 10, 11]))))
    # values = [5, 4, 1, 2, 2, 1, 4, -1]

    # local_maxima_with_index = pair_indices_with_values(
    #     values, find_local_maximas(values))
    # print(values)
    # print(' ' + "  ".join(' ' if (v, i)
    #       not in local_maxima_with_index else '*' for i, v in enumerate(values)))

    # rising_highs = list(yield_rising_highs(
    #     list(reversed(local_maxima_with_index))))

    # print(' ' + "  ".join(' ' if (v, i)
    #       not in rising_highs else '*' for i, v in enumerate(values)))
    # exit()
