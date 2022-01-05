from datetime import datetime, timedelta
import argparse

from src.grouped_aggs import fetch_grouped_aggs, get_cache_entry_refresh_time, get_current_cache_range, prepare_cache_grouped_aggs
from src.trading_day import generate_trading_days, get_market_open_on_day, is_during_market_hours, next_trading_day, now, previous_trading_day, today, today_or_previous_trading_day

POLYGON_CALLS_PER_MINUTE = 5  # estimating fetch time
# For reference, 2 years of download takes about 1.75 hours

if __name__ == '__main__':
    # cache info
    print("Cache Info:")
    cache_range = get_current_cache_range()
    if cache_range:
        cache_start = cache_range[0]
        cache_end = cache_range[1]

        last_refresh_time_start, last_refresh_time_end = get_cache_entry_refresh_time(
            cache_start), get_cache_entry_refresh_time(cache_end)

        print("\tlast refreshed:", last_refresh_time_start,
              "to", last_refresh_time_end)
        print("\tcache start:", cache_start)
        print("\tcache end:", cache_end)
        print()
    else:
        print("\tno pre-existing cache")

    market_now = now()

    market_today = today(market_now)

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)

    args = parser.parse_args()

    if args.end == "today":
        end = market_today
    else:
        end = today_or_previous_trading_day(
            datetime.strptime(args.end, "%Y-%m-%d").date())

    assert end <= market_today, "cannot query the future"
    if end == market_today and market_now < get_market_open_on_day(market_today):
        print("WARNING: cannot query today's data before market open, using previous trading day instead")
        end = previous_trading_day(market_today)

    if "end-" in args.start:
        years = int(args.start.replace("end-", ""))
        start = today_or_previous_trading_day(
            end - timedelta(days=365 * years))
        print(f"checking whether API allows us to go back {years} years")
        while True:
            try:
                fetch_grouped_aggs(start)  # no cache
                break
            except Exception as e:
                if e.response.status_code == 403:
                    print(f"{start} is too far back, trying next trading day")
                    start = next_trading_day(start)
                    continue
                raise e
    else:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()

    assert start < end

    # its fine if starting on a holiday, fetches it just the same
    print("start:", start)
    print("end:", end)
    print()

    # estimating fetch time
    weekdays = len(list(generate_trading_days(start, end)))
    print("weekdays:", weekdays)
    estimated_fetch_time = timedelta(
        minutes=weekdays / POLYGON_CALLS_PER_MINUTE)
    print("estimated fetch time:", estimated_fetch_time)
    estimated_end = market_now + estimated_fetch_time
    print("estimated end:", estimated_end)
    print()

    # Do not allow cache building during market hours, since it consumes all our rate limit
    # (I'm OK with quota consumption involved in `start` value interpretation.)
    if is_during_market_hours(market_now):
        print("ERROR: market is currently open, cache preparation not allowed (consumes quota). Exiting.")
        # (if we were OK with quota consumption, we would want to make sure no splits are applied between beginning and end of fetching)
        exit(1)

    if is_during_market_hours(estimated_end + timedelta(minutes=1)):  # +1m => cushion
        print("ERROR: market will be open when cache preparation completes, cache preparation not allowed (consumes quota). Exiting.")
        exit(1)

    print("checking if update needed...")
    print()

    prepare_cache_grouped_aggs(start, end)
