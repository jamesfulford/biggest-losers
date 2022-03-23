from datetime import date
from importlib import import_module
import logging
from types import ModuleType
from typing import Callable, cast
from src.data.finnhub.finnhub import CandleIntraday, get_candles

from src.data.polygon.grouped_aggs import Ticker
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.trading_day import today


CandleGetter = Callable[[str, str, date, date], list[CandleIntraday]]
PrescannerFilter = Callable[[list[Ticker], date], list[Ticker]]
ScannerFilter = Callable[[list[Ticker], date, CandleGetter], list[Ticker]]
Scanner = Callable[[], list[Ticker]]


def _get_scanner_module(scanner: str) -> ModuleType:
    assert scanner.replace("_", "").isalpha()
    return import_module("src.scan." + scanner)


def get_scanner_filter(scanner: str) -> ScannerFilter:
    module = _get_scanner_module(scanner)
    return module.scanner


def get_prescanner_filter(scanner: str) -> PrescannerFilter:
    module = _get_scanner_module(scanner)
    return module.prescanner


def get_leadup_period(scanner: str) -> int:
    module = _get_scanner_module(scanner)
    return module.LEADUP_PERIOD


def get_scanner(scanner_name: str) -> Scanner:
    scanner_filter = get_scanner_filter(scanner_name)

    # TODO: make everywhere calling this get the candidates themselves and apply filters instead
    def get_scan_results():
        tickers = get_all_tickers_on_day(today(), skip_cache=True)
        # TODO: remove this cast, get_candles and CandleGetter types not aligned
        # call it intraday_candle_getter
        return scanner_filter(tickers, today(), cast(CandleGetter, get_candles))

    return get_scan_results
