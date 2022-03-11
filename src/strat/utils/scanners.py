from datetime import date
from importlib import import_module
from typing import Callable

from src.data.polygon.grouped_aggs import Ticker
from src.trading_day import today


def get_scanner(scanner: str) -> Callable[[], list[Ticker]]:
    assert scanner.replace("_", "").isalpha()
    module = import_module("src.scan." + scanner)

    def get_scan_results():
        return module.get_all_candidates_on_day(today(), skip_cache=True)

    return get_scan_results
