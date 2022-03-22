from datetime import date
from importlib import import_module
import logging
from types import ModuleType
from typing import Callable
from src.data.finnhub.finnhub import CandleIntraday

from src.data.polygon.grouped_aggs import Ticker
from src.trading_day import today


CandleGetter = Callable[[str, str, date, date], list[CandleIntraday]]
ScannerFilter = Callable[[list[Ticker], date, CandleGetter], list[Ticker]]
Scanner = Callable[[], list[Ticker]]


def _get_scanner_module(scanner: str) -> ModuleType:
    assert scanner.replace("_", "").isalpha()
    return import_module("src.scan." + scanner)


def get_scanner(scanner: str) -> Scanner:
    module = _get_scanner_module(scanner)

    def get_scan_results():
        return module.get_all_candidates_on_day(today(), skip_cache=True)

    return get_scan_results


def get_scanner_filter(scanner: str) -> ScannerFilter:
    module = _get_scanner_module(scanner)

    def get_scan_results(tickers: list[Ticker], day: date, get_candles: CandleGetter, **kwargs) -> list[Ticker]:
        return module.filter_candidates_on_day(tickers, day, get_candles, **kwargs)

    return get_scan_results


def get_leadup_period(scanner: str) -> int:
    module = _get_scanner_module(scanner)

    try:
        return module.LEADUP_PERIOD
    except AttributeError:
        logging.warning(
            "No LEADUP_PERIOD defined for scanner %s, assuming 0", scanner)
        return 0
