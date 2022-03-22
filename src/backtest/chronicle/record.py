# record chronicle live

from datetime import time
import logging
import os
from typing import cast

from src import jsonl_dump
from src.strat.utils.scanners import get_scanner
from src.trading_day import now
from requests import HTTPError

from src.wait import get_next_minute_mark, wait_until


def should_continue():
    return now().time() < time(16, 0)


def loop(scanner: str, output_path: str):
    while should_continue():
        try:
            execute_phases(scanner, output_path)
        except HTTPError as e:
            logging.exception(
                f"HTTP {e.response.status_code} {e.response.text}")
        except Exception as e:
            logging.exception(f"Unexpected Exception")


def execute_phases(scanner: str, output_path: str):
    wait_until(get_next_minute_mark(now()))
    get_candidates = get_scanner(scanner)
    candidates = cast(list[dict], get_candidates())
    jsonl_dump.append_jsonl(output_path, candidates)


def main():
    # TODO: argparse
    # TODO: git commit id in path
    scanner = 'meemaw'
    output_path = 'data/meemwaw/live.jsonl'

    from src.pathing import get_paths

    path = get_paths()['data']['dir']

    output_path = os.path.join(
        path, 'chronicles', 'live', f'{now().date().isoformat()}.jsonl')

    try:
        os.makedirs(os.path.dirname(output_path))
    except FileExistsError:
        pass
    except:
        logging.exception("Could not create directory")

    logging.info(f"Recording live data for {scanner}")

    loop(scanner, output_path)
