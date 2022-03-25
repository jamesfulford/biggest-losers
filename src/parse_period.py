
import argparse
from datetime import date, datetime, timedelta
import logging
from typing import Tuple, cast
from src.trading_day import get_market_open_on_day, now, previous_trading_day, today, today_or_previous_trading_day


def add_range_args(parser: argparse.ArgumentParser, required=True) -> argparse.ArgumentParser:
    parser.add_argument("--start", type=str, required=required)
    parser.add_argument("--end", type=str, required=required)
    return parser


def interpret_args(args: argparse.Namespace) -> Tuple[date, date]:
    market_now = now()
    market_today = today(market_now)

    if args.end == "today":
        end = market_today
    else:
        end = today_or_previous_trading_day(
            datetime.strptime(args.end, "%Y-%m-%d").date()
        )

    assert end <= market_today, "cannot query the future"

    if end == market_today and market_now < cast(date, get_market_open_on_day(today_or_previous_trading_day(market_today))):
        logging.warning(
            "cannot query today's data before market open, using previous trading day instead"
        )
        end = previous_trading_day(market_today)

    start = market_today
    if "end-" in args.start:
        start_str = args.start.replace("end-", "")
        if start_str.endswith("d"):
            days = int(start_str.replace("d", ""))
            start = today_or_previous_trading_day(
                end - timedelta(days=days))
        elif start_str.endswith('y'):
            years = int(start_str.replace("y", ""))
            start = today_or_previous_trading_day(
                end - timedelta(days=365 * years))

    else:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()

    assert start < end

    return start, end


def main():
    parser = argparse.ArgumentParser()
    parser = add_range_args(parser)

    args = parser.parse_args()

    start, end = interpret_args(args)

    print(start, end)

    class A:
        start: str
        end: str

    a = A()
    a.start = "2020-01-01"
    a.end = "2022-01-03"
    start, end = interpret_args(cast(argparse.Namespace, a))
    print(start, end)
    assert start == date(2020, 1, 1)
    assert end == date(2022, 1, 3)

    # start before end case
    a = A()
    a.start = "2020-01-02"
    a.end = "2020-01-01"
    try:
        start, end = interpret_args(cast(argparse.Namespace, a))
        raise Exception("Was expecting an error")
    except AssertionError:
        pass
    except:
        raise
    print(start, end)

    # today and end-year case
    a = A()
    a.start = "end-1y"
    a.end = "today"
    start, end = interpret_args(cast(argparse.Namespace, a))
    print(start, end)
    assert end - start <= timedelta(days=366)
    assert end - start >= timedelta(days=364)

    # today and end-day case
    a = A()
    a.start = "end-10d"
    a.end = "today"
    start, end = interpret_args(cast(argparse.Namespace, a))
    print(start, end)
    assert end - start == timedelta(days=10)
