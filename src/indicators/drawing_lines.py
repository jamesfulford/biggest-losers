from datetime import date, timedelta
from typing import Optional
from src.data.finnhub.finnhub import get_1m_candles, get_d_candles
from src.indicators.drawing_lines_logic import get_james_lines
from src.trading_day import previous_trading_day, today


def find_james_lines(symbol: str, day: Optional[date] = None, ignore_last_n_5m_candles: int = 5) -> Optional[list[Line]]:
    this_day = today() if day is None else day
    # Use 1m candles and aggregate to 5m so we get more cache hits in backtests (no other code uses 5m)
    candles_1m = get_1m_candles(symbol, this_day -
                                timedelta(days=7), this_day)
    if not candles_1m:
        return None

    candles_d = get_d_candles(symbol, today() -
                              timedelta(days=180), previous_trading_day(today()))
    if not candles_d:
        return None

    return get_james_lines(candles_1m, candles_d, ignore_last_n_5m_candles)


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
