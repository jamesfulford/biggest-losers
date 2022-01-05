from datetime import date, datetime, timedelta
import argparse

from src.grouped_aggs import get_current_cache_range, prepare_cache_grouped_aggs

POLYGON_CALLS_PER_MINUTE = 5  # estimating fetch time

if __name__ == '__main__':
    today = date.today()

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)

    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()

    assert start < end

    print("start:", start)
    print("end:", end)
    print()

    cache_range = get_current_cache_range()
    if cache_range:
        cache_start = cache_range[0]
        cache_end = cache_range[1]
        print("cache start:", cache_start)
        print("cache end:", cache_end)
        print()

    # estimating fetch time
    dates = (start + timedelta(idx + 1)
             for idx in range((end - start).days))
    weekdays = sum(1 for day in dates if day.weekday() < 5)
    print("weekdays:", weekdays)
    print("estimated fetch time:", timedelta(
        minutes=weekdays / POLYGON_CALLS_PER_MINUTE))
    print()

    print("checking if update needed...")
    print()

    prepare_cache_grouped_aggs(start, end)
