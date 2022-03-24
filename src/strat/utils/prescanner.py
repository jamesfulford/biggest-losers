from datetime import date
from typing import Callable
from src.data.polygon.grouped_aggs import Ticker
from src.strat.utils.scanners import PrescannerFilter, ScannerFilter


def build_prescanner_with_empty_candle_getter(scanner: ScannerFilter) -> PrescannerFilter:
    def _prescanner(tickers: list[Ticker], day: date, **kwargs) -> list[Ticker]:
        return scanner(tickers, day, lambda _1, _2, _3, _4: [], **kwargs)
    return _prescanner


def with_kwargs(prescanner: PrescannerFilter, **kwargs) -> PrescannerFilter:
    def _prescanner(tickers: list[Ticker], day: date) -> list[Ticker]:
        return prescanner(tickers, day, **kwargs)
    return _prescanner


def with_high_bias_prescan_strategy(scanner: PrescannerFilter) -> PrescannerFilter:
    """
    Use to map 'h' to 'c' so scanners biased toward highs (e.g. has to be 5% up from previous day close) can cast a wider net during prescanning.
    """

    def _prescanner(tickers: list[Ticker], day: date, **kwargs) -> list[Ticker]:
        for ticker in tickers:
            ticker['c'] = ticker['h']
        tickers = scanner(tickers, day, **kwargs)
        return tickers

    return _prescanner


def with_low_bias_prescan_strategy(scanner: PrescannerFilter) -> PrescannerFilter:
    """
    Use to map 'l' to 'c' so scanners biased toward highs (e.g. has to be 5% down from previous day close) can cast a wider net during prescanning.
    """

    def _prescanner(tickers: list[Ticker], day: date, **kwargs) -> list[Ticker]:
        for ticker in tickers:
            ticker['c'] = ticker['l']
        tickers = scanner(tickers, day, **kwargs)
        return tickers

    return _prescanner
