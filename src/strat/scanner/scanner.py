import json
from datetime import datetime, timedelta, date
import logging
from importlib import import_module

from requests.exceptions import HTTPError

from src.trading_day import now, today
from src.wait import wait_until


ALGO_NAME = "scanner"


def next_minute_mark(dt: datetime) -> datetime:
    return dt - timedelta(microseconds=dt.microsecond, seconds=dt.second) + timedelta(minutes=1)


def loop(scanner: str):
    while True:
        try:
            execute_phases(scanner)
        except HTTPError as e:
            logging.exception(
                f"HTTP {e.response.status_code} {e.response.text}")
        except Exception as e:
            logging.exception(f"Unexpected Exception")


def execute_phases(scanner: str):
    #
    # Execution Phase
    #
    next_interval_start = next_minute_mark(now())

    #
    # Scan
    #
    # NOTE: Cache for multiple previous days must be prepared beforehand in order to work.
    day = date(2021, 12, 28)  # TODO: remove
    # day = today()

    module = import_module("src.scan." + scanner)
    tickers = module.get_all_candidates_on_day(day, skip_cache=True)

    if scanner == "rollercoasters":
        print("-"*20, "oOo", now().strftime("%H:%M"), "oOo", "-"*20)
        for candidate in tickers[:10]:
            print(
                f"{candidate['T'] : ^10} \t| {candidate['c'] : ^10} \t| {candidate['v']/1000000 :>10.2f}M \t| {candidate['percent_change_days_ago'] : .0%}")
    else:
        for candidate in tickers[:10]:
            print(json.dumps(candidate, sort_keys=True))

    # NOCOMMIT
    wait_until(next_interval_start)


def main():
    import sys

    scanner = sys.argv[1]
    assert scanner.isalpha()
    print(scanner)
    logging.info(f"Starting live scanning")
    loop(scanner)


if __name__ == "__main__":
    main()
