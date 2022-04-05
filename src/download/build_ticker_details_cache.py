import argparse
from datetime import date, timedelta

from requests import HTTPError

from src.data.polygon.asset_class import is_etf, is_right, is_stock, is_unit, is_warrant
from src.parse_period import add_range_args, interpret_args
from src.trading_day import generate_trading_days, next_trading_day, today
import logging


def get_data(day: date) -> None:
    logging.info(f"Updating symbol details cache for {day}")
    is_stock("ZZZZZ", day=day)
    is_etf("ZZZZZ", day=day)
    is_warrant("ZZZZZ", day=day)
    is_right("ZZZZZ", day=day)
    is_unit("ZZZZZ", day=day)


def main():
    parser = argparse.ArgumentParser()
    parser = add_range_args(parser)
    args = parser.parse_args()
    start, end = interpret_args(args)

    if (today() - start) > timedelta(days=500):
        logging.info(f"checking whether API allows us to go back to {start}")
        while True:
            try:
                get_data(start)  # no cache
                break
            except HTTPError as e:
                if e.response.status_code == 403:
                    logging.info(
                        f"{start} is too far back, trying next trading day")
                    start = next_trading_day(start)
                    continue
                raise e

    logging.info(
        f"Started updating symbol details cache from {start} to {end}...")
    for day in generate_trading_days(start, end):
        get_data(day)

    logging.info("Done updating symbol details cache.")


if __name__ == "__main__":
    main()
