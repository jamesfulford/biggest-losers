from datetime import date, datetime
import os

from src.polygon import is_ticker_one_of


def is_stock(ticker, day: date = None) -> bool:
    # "ADRC" -> sometimes don't clear or are supported by brokers
    # also can be China
    return is_ticker_one_of(ticker, ["CS", "PFD"], day=day)


def is_etf(ticker, day: date = None) -> bool:
    # "ETN" -> can take longer to clear
    return is_ticker_one_of(ticker, ["ETF", "ETN"], day=day)


def is_warrant(ticker, day: date = None) -> bool:
    # "ADRW" -> Polygon showed 0 on 2022-01-15, let's save a request
    return is_ticker_one_of(ticker, ["WARRANT"], day=day)


def is_warrant_format(ticker: str) -> bool:
    return ticker.upper().endswith("W") or ".WS" in ticker.upper()


def is_right(ticker, day: date = None) -> bool:
    # "ADRR"
    return is_ticker_one_of(ticker, ["RIGHT"], day=day)


def is_unit(ticker, day: date = None) -> bool:
    return is_ticker_one_of(ticker, ["UNIT"], day=day)


def is_unit_format(ticker: str) -> bool:
    return ticker.upper().endswith("U") or ".U" in ticker.upper()

# Not covered:
# - SP (Structured Product)
# - BOND
# - FUND
# - BASKET
# - LT (Liquidating Trust)

#
# Skipping days
#


dir_of_script = os.path.dirname(os.path.abspath(__file__))
days_to_skip_csv_path = os.path.abspath(
    os.path.join(dir_of_script, "..", "days_to_skip.csv")
)


def get_skipped_days():
    lines = []
    with open(days_to_skip_csv_path, "r") as f:
        lines.extend(f.readlines())

    headers = lines[0].strip().split(",")
    # remove newlines and header row
    lines = [l.strip() for l in lines[1:]]

    # convert to dicts
    raw_dict_lines = [dict(zip(headers, l.strip().split(","))) for l in lines]

    lines = [
        {"date": datetime.strptime(
            d["date"], "%Y-%m-%d").date(), "reason": d["reason"]}
        for d in raw_dict_lines
    ]

    return lines


_skipped_days_set = set(
    map(lambda d: d["date"].strftime("%Y-%m-%d"), get_skipped_days())
)


def is_skipped_day(today):
    return today.strftime("%Y-%m-%d") in _skipped_days_set
