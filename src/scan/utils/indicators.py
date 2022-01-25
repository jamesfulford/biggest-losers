from datetime import date
from typing import Callable
import numpy as np
from talib.abstract import Function

from src.data.polygon.grouped_aggs import get_last_n_candles


def use_indicator(indicator: Function, **kwargs):
    def _talib_use(candles: list[dict]):
        inputs = {
            "open": np.array(list(map(lambda c: float(c["o"]), candles))),
            "high": np.array(list(map(lambda c: float(c["h"]), candles))),
            "low": np.array(list(map(lambda c: float(c["l"]), candles))),
            "close": np.array(list(map(lambda c: float(c["c"]), candles))),
            "volume": np.array(list(map(lambda c: float(c["v"]), candles))),
        }
        values = indicator(inputs, **kwargs)
        value = float(values[-1])
        return value
    return _talib_use


def extract_from_n_candles_ago(key: str, n: int):
    """
    n = 0 means today
    n = 1 means yesterday
    n = 2 means 2 days ago
    ...
    """
    def _extract_from_n_candles_ago(candles: list[dict]):
        return candles[-(n - 1)][key]
    return _extract_from_n_candles_ago


def from_yesterday_candle(key: str):
    return extract_from_n_candles_ago(key, 1)


def enrich_tickers_with_indicators(day: date, tickers: list[dict], indicators: dict[str, Callable], n=15):
    """
    Fetches last `n` daily candles and uses those to calculate provided indicators.
    Last value from each indicator is added to each ticker.
    To use talib, use `use_indicator` function and `talib.abstract.*` (ex: talib.abstract.RSI)
    """
    for ticker in tickers:
        daily_candles = get_last_n_candles(day, ticker["T"], n=n)
        if not daily_candles:
            continue
        daily_candles = list(reversed(daily_candles))

        for indicator_name, indicator in indicators.items():
            ticker[indicator_name] = indicator(daily_candles)
        yield ticker
