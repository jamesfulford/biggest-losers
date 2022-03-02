import json
from datetime import datetime, timedelta, date
import logging
from importlib import import_module
from pprint import pformat, pprint

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


def format_price(price: float):
    if price < 1.:
        return f"{price:.4f}".replace("0.", ".")
    else:
        return f"{price:.2f}" + "  "


def execute_phases(scanner: str):
    #
    # Execution Phase
    #
    next_interval_start = next_minute_mark(now())

    #
    # Scan
    #
    # NOTE: Cache for multiple previous days must be prepared beforehand in order to work.
    day = today()

    module = import_module("src.scan." + scanner)
    tickers = module.get_all_candidates_on_day(day, skip_cache=True)

    if scanner == "rollercoasters":
        print("-"*20, "oOo", now().strftime("%H:%M"), "oOo", "-"*20)
        for candidate in tickers[:10]:
            print(
                f"{candidate['T'] : ^10} \t| {candidate['c'] : ^10} \t| {candidate['v']/1000000 :>10.2f}M \t| {candidate['percent_change_days_ago'] : .0%}")
    elif scanner == "meemaw":
        print("-"*20, "oOo", now().strftime("%H:%M"), "oOo", "-"*20)
        for candidate in tickers[:10]:
            print(
                f"{candidate['T']:<5} | ${format_price(candidate['c']):>8} | {candidate['v']/1000000:>6.1f}M ({candidate['v']/candidate['float']:>5.0%} of fl) | {candidate['float']/1000000 :>6.1f}M fl | {candidate['percent_change']:>3.0%}")
    else:
        print("WARNING: no pretty printer found for scanner", scanner)
        for candidate in tickers[:10]:
            del candidate['t']
            del candidate['is_stock']
            del candidate['n']
            print(pformat(candidate, compact=True, depth=1).replace("\n", ""))
            # print(json.dumps(candidate, sort_keys=True))

    # NOCOMMIT
    wait_until(next_interval_start)


def main():
    import sys

    scanner = sys.argv[1]
    assert scanner.replace("_", "").isalpha()
    print(scanner)
    logging.info(f"Starting live scanning")
    loop(scanner)


if __name__ == "__main__":
    main()
