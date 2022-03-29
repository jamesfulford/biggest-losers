import argparse
from copy import deepcopy
from datetime import date, time
import logging
import os
from typing import Optional, cast
from requests import HTTPError

from src import jsonl_dump
from src.backtest.chronicle.read import get_scanner_recorded_chronicle_path
from src.data.finnhub.finnhub import get_candles
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.strat.utils.scanners import CandleGetter, Scanner, ScannerFilter, get_scanner, get_scanner_filter
from src.trading_day import now, today
from src.wait import get_next_minute_mark, wait_until
from src.pathing import get_paths


def should_continue():
    return now().time() < time(16, 0)


def loop(scanner_filters: dict[str, ScannerFilter]):
    while should_continue():
        try:
            execute_phases(scanner_filters)
        except HTTPError as e:
            logging.exception(
                f"HTTP {e.response.status_code} {e.response.text}")
        except Exception as e:
            logging.exception(f"Unexpected Exception")


def execute_phases(scanner_filters: dict[str, ScannerFilter]):
    next_min = get_next_minute_mark(now())
    wait_until(next_min)

    day = today()
    tickers = get_all_tickers_on_day(day)

    # TODO: run each loop in its own process, so one slow scanner doesn't block others
    for scanner_name, scanner_filter in scanner_filters.items():
        logging.info(f"Scanning {scanner_name}")
        copied_tickers = deepcopy(tickers)

        try:
            # TODO: remove this cast, get_candles and CandleGetter types not aligned
            # call it intraday_candle_getter
            candidates = scanner_filter(
                copied_tickers, day, cast(CandleGetter, get_candles))
        except Exception as e:
            logging.exception(f"Scanner {scanner_name} failed, skipping...")
            continue

        jsonl_dump.append_jsonl(get_scanner_recorded_chronicle_path(scanner_name, day), ({
            "now": next_min,
            "ticker": c,
        } for c in candidates))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=str)
    args = parser.parse_args()

    scanner_names = args.scanner.split(',')

    scanner_filters = {
        scanner_name: get_scanner_filter(scanner_name)
        for scanner_name in scanner_names
    }

    # pre-create folders
    for scanner_name in scanner_filters.keys():
        chronicle_path = get_scanner_recorded_chronicle_path(
            scanner_name, today())
        try:
            os.makedirs(os.path.dirname(chronicle_path))
        except FileExistsError:
            pass

    logging.info(f"Recording live data for {scanner_names}")

    loop(scanner_filters)
