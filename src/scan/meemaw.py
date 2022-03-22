import os
from typing import Callable, cast
from datetime import date, datetime, time, timedelta
import logging
from src import jsonl_dump

from src.criteria import is_stock
from src.data.finnhub.finnhub import get_candles
from src.data.yh.stats import get_short_interest
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, from_yesterday_candle
from src.trading_day import MARKET_TIMEZONE, generate_trading_days
from src.data.polygon.grouped_aggs import Ticker, get_cache_prepared_date_range_with_leadup_days
from src.data.finnhub.finnhub import get_candles


#
# _on_day: used for LIVE and BACKTEST
# - all filtering logic should be here
# - all critical indicators should be enriched in here
#
# Some tips:
# - try to filter on OHLCV first before getting daily candles or calculating indicators

from src.data.td.td import get_fundamentals

LEADUP_PERIOD = 1


def get_all_candidates_on_day(today: date, skip_cache=False):
    tickers = get_all_tickers_on_day(today, skip_cache=skip_cache)
    return filter_candidates_on_day(tickers, today, shallow_scan=not skip_cache)


class Candidate(Ticker):
    open_to_close_change: float
    is_stock: bool
    percent_change: float
    c_1d: float
    relative_volume: float
    shares_short: int
    short_interest: float
    float: int


def filter_candidates_on_day(provided_tickers: list[Ticker], today: date, _candle_getter: Callable = get_candles, shallow_scan=False) -> list[Candidate]:
    max_close_price = 5
    min_volume = 100_000
    min_open_to_close_change = 0
    min_percent_change = 0.05
    min_float, max_float = (1_000_000, 50_000_000)
    min_short_interest = 0.02
    top_n = 1

    tickers = provided_tickers  # typing doesn't like re-typing function parameters

    tickers = list(filter(lambda t: t["c"] < max_close_price, tickers))
    tickers = list(filter(lambda t: t["v"] > min_volume, tickers))

    tickers = cast(list[Candidate], tickers)

    for ticker in tickers:
        ticker["open_to_close_change"] = (
            ticker['c'] - ticker['o']) / ticker['o']
    tickers = list(
        filter(lambda t: t["open_to_close_change"] > min_open_to_close_change, tickers))

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_stock": is_stock,
    }))

    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "c_1d": from_yesterday_candle("c"),
    }, n=LEADUP_PERIOD + 1))
    for ticker in tickers:
        ticker["percent_change"] = (
            ticker["c"] - ticker["c_1d"]) / ticker["c_1d"]
    tickers = list(
        filter(lambda t: t["percent_change"] > min_percent_change, tickers))

    # Low float
    # TODO: instruct `get_fundamentals` to check cache for data nearest `day`
    fundamentals = get_fundamentals(list(map(lambda t: t["T"], tickers)))
    tickers = list(filter(lambda t: t["T"] in fundamentals, tickers))
    for ticker in tickers:
        ticker['float'] = fundamentals[ticker['T']]['shares']['float']
    tickers = list(
        filter(lambda t: t['float'] < max_float and t['float'] > min_float, tickers))

    # High relative volume
    for ticker in tickers:
        ticker['relative_volume'] = ticker['v'] / \
            ticker['float']  # (because >, no divide by zero)
    tickers = list(filter(lambda t: t['relative_volume'], tickers))

    if not shallow_scan:
        # Highest volume first
        tickers.sort(key=lambda t: t['v'], reverse=True)

        # only compute tickers necessary (top_n), less quota usage
        new_tickers = []
        for ticker in tickers:
            # Short Interest
            # (done last to save very restricted API call quota)
            short_data = get_short_interest(ticker["T"], today)
            if not short_data:
                continue
            ticker["shares_short"] = short_data["shares_short"]
            ticker["short_interest"] = ticker["shares_short"] / \
                ticker["float"]
            if not (ticker["short_interest"] > min_short_interest):
                continue

            new_tickers.append(ticker)
            if len(new_tickers) >= top_n:
                break
        tickers = new_tickers

    return tickers
