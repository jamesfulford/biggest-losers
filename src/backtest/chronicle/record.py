import argparse
from copy import deepcopy
from datetime import date, time
import logging
import os
from typing import Optional, cast
from requests import HTTPError

from src import jsonl_dump
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

    for scanner_name, scanner_filter in scanner_filters.items():
        logging.info(f"Scanning {scanner_name}")
        copied_tickers = deepcopy(tickers)
        # TODO: remove this cast, get_candles and CandleGetter types not aligned
        # call it intraday_candle_getter
        candidates = scanner_filter(
            copied_tickers, day, cast(CandleGetter, get_candles))

        try:
            os.makedirs(os.path.dirname(
                get_scanner_live_chronicle_path(scanner_name, day)))
        except FileExistsError:
            pass

        jsonl_dump.append_jsonl(get_scanner_live_chronicle_path(scanner_name, day), ({
            "now": next_min,
            "ticker": c,
        } for c in candidates))


def get_scanner_live_chronicle_path(scanner_name: str, day: date, commit_id: Optional[str] = None):
    if not commit_id:
        commit_id = os.environ.get("GIT_COMMIT", "dev")

    path = get_paths()['data']['dir']

    return os.path.join(
        path, 'chronicles', scanner_name, 'live', f'{day.isoformat()}-{commit_id}.jsonl')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=str)
    args = parser.parse_args()

    scanner_names = args.scanner.split(',')

    scanner_filters = {
        scanner_name: get_scanner_filter(scanner_name)
        for scanner_name in scanner_names
    }

    logging.info(f"Recording live data for {scanner_names}")

    loop(scanner_filters)
