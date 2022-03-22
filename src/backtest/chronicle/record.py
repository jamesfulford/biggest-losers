import argparse
from datetime import date, time
import logging
import os
from typing import Optional, cast
from requests import HTTPError

from src import jsonl_dump
from src.strat.utils.scanners import Scanner, get_scanner
from src.trading_day import now
from src.wait import get_next_minute_mark, wait_until
from src.pathing import get_paths


def should_continue():
    return now().time() < time(16, 0)


def loop(scanner: Scanner, output_path: str):
    while should_continue():
        try:
            execute_phases(scanner, output_path)
        except HTTPError as e:
            logging.exception(
                f"HTTP {e.response.status_code} {e.response.text}")
        except Exception as e:
            logging.exception(f"Unexpected Exception")


def execute_phases(scanner: Scanner, output_path: str):
    next_min = get_next_minute_mark(now())
    wait_until(next_min)
    candidates = cast(list[dict], scanner())
    jsonl_dump.append_jsonl(output_path, ({
        "now": next_min,
        "ticker": c,
    } for c in candidates))


def get_scanner_live_chronicle_path(scanner: str, day: date, commit_id: Optional[str] = None):
    if not commit_id:
        commit_id = os.environ.get("GIT_COMMIT", "dev")

    path = get_paths()['data']['dir']

    return os.path.join(
        path, 'chronicles', scanner, 'live', f'{day.isoformat()}-{commit_id}.jsonl')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=str)
    args = parser.parse_args()

    scanner_name = args.scanner
    scanner = get_scanner(scanner_name)

    logging.info(f"Recording live data for {scanner_name}")

    output_path = get_scanner_live_chronicle_path(scanner_name, now().date())
    loop(scanner, output_path)
