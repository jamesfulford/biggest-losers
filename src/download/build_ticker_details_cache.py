import argparse
from datetime import datetime, timedelta
from src.criteria import is_etf, is_right, is_stock, is_unit, is_warrant
from src.parse_period import add_range_args, interpret_args
from src.trading_day import generate_trading_days, now, today, today_or_previous_trading_day
import logging


def main():
    parser = argparse.ArgumentParser()
    parser = add_range_args(parser)
    args = parser.parse_args()
    start, end = interpret_args(args)

    logging.info(
        f"Started updating symbol details cache from {start} to {end}...")
    for day in generate_trading_days(start, end):
        logging.info(f"Updating symbol details cache for {day}")
        is_stock("ZZZZZ", day=day)
        is_etf("ZZZZZ", day=day)
        is_warrant("ZZZZZ", day=day)
        is_right("ZZZZZ", day=day)
        is_unit("ZZZZZ", day=day)

    logging.info("Done updating symbol details cache.")


if __name__ == "__main__":
    main()
