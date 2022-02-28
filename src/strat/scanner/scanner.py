import json
from datetime import datetime, timedelta, date
import logging

from requests.exceptions import HTTPError


from src.trading_day import now, today
from src.wait import wait_until

from src.scan.rollercoasters import get_all_candidates_on_day

ALGO_NAME = "scanner"


def next_minute_mark(dt: datetime) -> datetime:
    return dt - timedelta(microseconds=dt.microsecond, seconds=dt.second) + timedelta(minutes=1)


def loop():
    while True:
        try:
            execute_phases()
        except HTTPError as e:
            logging.exception(
                f"HTTP {e.response.status_code} {e.response.text}")
        except Exception as e:
            logging.exception(f"Unexpected Exception")


def execute_phases():
    #
    # Execution Phase
    #
    next_interval_start = next_minute_mark(now())
    wait_until(next_interval_start)

    #
    # Scan
    #
    # Cache for multiple previous days must be prepared beforehand in order to work.
    tickers = get_all_candidates_on_day(date(2021, 12, 28), skip_cache=True)

    print("-"*20, "oOo", now().strftime("%H:%M"), "oOo", "-"*20)
    for candidate in tickers[:10]:
        print(
            f"{candidate['T'] : ^10} \t| {candidate['c'] : ^10} \t| {candidate['v']/1000000 :>10.2f}M \t| {candidate['percent_change_days_ago'] : .0%}")


def main():
    logging.info(f"Starting live scanning")
    loop()


if __name__ == "__main__":
    main()
