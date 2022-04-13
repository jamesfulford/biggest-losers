
from datetime import date, datetime, timedelta
from typing import Iterable, Tuple, TypeVar, TypedDict, Union
from src.data.finnhub.aggregate_candles import aggregate_intraday_candles, filter_candles_during_market_hours
from src.data.types.candles import Candle, CandleInterday, CandleIntraday


class Line(TypedDict):
    time: Union[date, datetime]
    value: float
    source: str
    state: str


T = TypeVar("T")


def pair_indices_with_values(values: list[T], indices: list[int]) -> list[Tuple[T, int]]:
    return [(values[i], i) for i in indices]


def yield_rising_highs(values: list):
    if len(values) <= 2:
        return

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
    if len(values) <= 2:
        return []

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
    if not candles:
        return [], []

    highs = [c['high'] for c in candles]
    local_maxima_with_index = pair_indices_with_values(
        highs, find_local_maximas(highs))
    rising_highs = list(yield_rising_highs(
        list(reversed(local_maxima_with_index)))) if local_maxima_with_index else []
    rising_high_candles = [candles[i] for _, i in rising_highs]
    high_lines = [(c.get('datetime', c.get('date')), c['high'])
                  for c in rising_high_candles]

    negative_lows = [-c['low'] for c in candles]
    local_maxima_with_index = pair_indices_with_values(
        negative_lows, find_local_maximas(negative_lows))
    declining_lows_with_negated_values = list(yield_rising_highs(
        list(reversed(local_maxima_with_index)))) if local_maxima_with_index else []
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


def get_james_lines(candles_1m: list[CandleIntraday], candles_d: list[CandleInterday], ignore_last_n_5m_candles: int = 5) -> list[Line]:
    candles_1m = filter_candles_during_market_hours(candles_1m)
    # TODO: candles_1m are unadjusted candles, need to detect if is an issue
    candles_5m = aggregate_intraday_candles(candles_1m, minute_candles=5)
    candles_5m = candles_5m[:-ignore_last_n_5m_candles]

    candles_5m = [c for c in candles_5m if c['datetime']
                  > candles_5m[-1]['datetime'] - timedelta(days=7)]
    candles_d = [c for c in candles_d if c['date'] >
                 candles_d[-1]['date'] - timedelta(days=180)]

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

    if high_lines_today_intraday:
        today_high = high_lines_today_intraday[-1]['value']
        for line in past_high_lines:
            if line['value'] <= today_high:
                line['state'] = 'inactive'

    if low_lines_today_intraday:
        today_low = low_lines_today_intraday[-1]['value']
        for line in past_low_lines:
            if line['value'] >= today_low:
                line['state'] = 'inactive'

    return sorted(past_low_lines + low_lines_today_intraday + past_high_lines + high_lines_today_intraday, key=lambda x: x['value'], reverse=True)
