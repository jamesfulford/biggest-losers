from datetime import date, datetime, timedelta
import argparse
import logging
from typing import cast
from requests import HTTPError
from src.cache import clear_json_cache

from src.data.polygon.grouped_aggs import (
    fetch_grouped_aggs,
    get_cache_entry_refresh_time,
    get_current_cache_range,
    prepare_cache_grouped_aggs,
)
from src.parse_period import add_range_args, interpret_args
from src.trading_day import (
    generate_trading_days,
    get_market_open_on_day,
    is_during_market_hours,
    next_trading_day,
    now,
    previous_trading_day,
    today,
    today_or_previous_trading_day,
)

POLYGON_CALLS_PER_MINUTE = 5  # estimating fetch time
# For reference, 2 years of download takes about 1.75 hours


def main():

    cache_range = get_current_cache_range()
    if cache_range:
        cache_start = cache_range[0]
        cache_end = cache_range[1]

        last_refresh_time_start, last_refresh_time_end = get_cache_entry_refresh_time(
            cache_start
        ), get_cache_entry_refresh_time(cache_end)

        logging.info(
            f"cache last refreshed: {last_refresh_time_start} to {last_refresh_time_end}")
        logging.info(f"cache start: {cache_start}")
        logging.info(f"cache end: {cache_end}")
    else:
        logging.info("no pre-existing cache")

    market_now = now()
    market_today = today(market_now)

    parser = argparse.ArgumentParser()
    parser = add_range_args(parser)
    parser.add_argument("--force", action="store_true", default=False)
    parser.add_argument("--clear", action="store_true", default=False)
    args = parser.parse_args()

    if args.clear:
        logging.info("Clearing cache before re-building...")
        clear_json_cache("polygon/grouped_aggs/")

    start, end = interpret_args(args)

    if (start - market_today) > timedelta(days=500):
        logging.info(f"checking whether API allows us to go back to {start}")
        while True:
            try:
                fetch_grouped_aggs(start)  # no cache
                break
            except HTTPError as e:
                if e.response.status_code == 403:
                    logging.info(
                        f"{start} is too far back, trying next trading day")
                    start = next_trading_day(start)
                    continue
                raise e

    assert start < end

    # its fine if starting on a holiday, fetches it just the same
    logging.info(f"{start=}")
    logging.info(f"{end=}")

    # estimating fetch time
    weekdays = len(list(generate_trading_days(start, end)))
    logging.info(f"{weekdays=}")
    estimated_fetch_time = timedelta(
        minutes=weekdays / POLYGON_CALLS_PER_MINUTE)
    logging.info(f"{estimated_fetch_time=}")
    estimated_end = market_now + estimated_fetch_time
    logging.info(f"{estimated_end=}")

    # Do not allow cache building during market hours, since it consumes all our rate limit
    # (I'm OK with quota consumption involved in `start` value interpretation.)
    if not args.force:
        if is_during_market_hours(market_now):
            logging.error(
                "market is currently open, cache preparation not allowed (consumes quota). Exiting."
            )
            # (if we were OK with quota consumption, we would want to make sure no splits are applied between beginning and end of fetching)
            exit(1)

        if is_during_market_hours(
            estimated_end + timedelta(minutes=1)
        ):  # +1m => cushion
            logging.error(
                "market will be open when cache preparation completes, cache preparation not allowed (consumes quota). Exiting."
            )
            exit(1)

    logging.info("checking if update needed...")

    prepare_cache_grouped_aggs(start, end)


if __name__ == "__main__":
    main()
