import argparse
from copy import deepcopy
from datetime import date, time
import logging
import os
from typing import cast
from requests import HTTPError
from src.backtest.chronicle import crud, types

from src.data.finnhub.finnhub import get_candles
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.scan.utils.scanners import CandleGetter, ScannerFilter, get_scanner_filter
from src.trading_day import now, today, get_market_close_on_day
from src.wait import get_next_minute_mark, wait_until


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

        crud.append_snapshots(build_chronicle_name(scanner_name, day), snapshots=[types.Snapshot(now=next_min, entries=[
                              types.ChronicleEntry(ticker=ticker, now=next_min) for ticker in candidates])])


def build_chronicle_name(scanner_name: str, day: date) -> str:
    return f"live-{scanner_name}-{day}"


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
        crud.create(build_chronicle_name(scanner_name, today()), metadata=types.ChronicleMeta(
            start=now(), end=get_market_close_on_day(now()) or now(), commit=os.environ.get("GIT_COMMIT", 'dev'), classification='recorded', origin=scanner_name))

    logging.info(f"Recording live data for {scanner_names}")

    loop(scanner_filters)
