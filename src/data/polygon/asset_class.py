from datetime import date
from typing import Optional

from src.data.polygon.polygon import is_ticker_one_of


def is_stock(ticker, day: Optional[date] = None) -> bool:
    # "ADRC" -> sometimes don't clear or are supported by brokers, also can be China
    return is_ticker_one_of(ticker, ["CS", "PFD", "ADRC"], day=day)


def is_etf(ticker, day: Optional[date] = None) -> bool:
    # "ETN" -> can take longer to clear?
    return is_ticker_one_of(ticker, ["ETF", "ETN"], day=day)


def is_warrant(ticker, day: Optional[date] = None) -> bool:
    # NOTE: "ADRW" -> Polygon showed 0 on 2022-01-15, let's save a request
    return is_ticker_one_of(ticker, ["WARRANT"], day=day)


def is_warrant_format(ticker: str) -> bool:
    return ticker.upper().endswith("W") or ".WS" in ticker.upper()


def is_right(ticker, day: Optional[date] = None) -> bool:
    # NOTE: "ADRR"
    return is_ticker_one_of(ticker, ["RIGHT"], day=day)


def is_unit(ticker, day: Optional[date] = None) -> bool:
    return is_ticker_one_of(ticker, ["UNIT"], day=day)


def is_unit_format(ticker: str) -> bool:
    return ticker.upper().endswith("U") or ".U" in ticker.upper()

# Not covered:
# - SP (Structured Product)
# - BOND
# - FUND
# - BASKET
# - LT (Liquidating Trust)
