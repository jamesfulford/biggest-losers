from datetime import date
import logging
from typing import Iterable, cast

from src.criteria import is_etf, is_right, is_stock, is_unit, is_warrant
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, use_indicator
from src.trading_day import generate_trading_days
from src.data.polygon.grouped_aggs import Ticker, get_cache_prepared_date_range_with_leadup_days
from src.csv_dump import write_csv

from talib.abstract import RSI

#
# _on_day: used for LIVE and BACKTEST
# - all filtering logic should be here
# - all critical indicators should be enriched in here
#
# Some tips:
# - try to filter on OHLCV first before getting daily candles or calculating indicators


class Candidate(Ticker):
    is_etf: bool
    is_right: bool
    is_stock: bool
    is_unit: bool
    is_warrant: bool

    rsi: float


class CandidateWithDayOfAction(Candidate):
    day_of_action: date


def get_all_candidates_on_day(today: date, skip_cache=False) -> list[Candidate]:
    tickers = get_all_tickers_on_day(today, skip_cache=skip_cache)
    tickers = list(filter(lambda t: t["c"] < 5, tickers))
    tickers = list(filter(lambda t: t["v"] > 300000, tickers))

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_etf": is_etf,
        "is_right": is_right,
        "is_stock": is_stock,
        "is_unit": is_unit,
        "is_warrant": is_warrant,
    }))

    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "rsi": use_indicator(RSI, timeperiod=14),
    }, n=15))

    tickers = cast(list[Candidate], tickers)

    tickers = list(filter(lambda t: t["rsi"] < 30, tickers))

    return tickers


def get_all_candidates_between_days(start: date, end: date) -> Iterable[CandidateWithDayOfAction]:
    for day in generate_trading_days(start, end):
        for candidate in get_all_candidates_on_day(day) or []:
            new_candidate = cast(
                CandidateWithDayOfAction, candidate)
            new_candidate["day_of_action"] = day
            yield new_candidate


def build_row(candidate: dict):
    return {
        "day_of_action": candidate['day_of_action'],
        # ticker insights
        "T": candidate['T'],
        "is_stock": candidate['is_stock'],
        "is_etf": candidate['is_etf'],
        "is_warrant": candidate['is_warrant'],
        "is_unit": candidate['is_unit'],
        "is_right": candidate['is_right'],

        # day_of_action stats
        "o": candidate["o"],
        "h": candidate["h"],
        "l": candidate["l"],
        "c": candidate["c"],
        "v": candidate["v"],
        "n": candidate["n"],

        # indicators
        "rsi": candidate["rsi"],
        "vw": candidate["vw"],
    }


def prepare_biggest_losers_csv(path: str, start: date, end: date):
    write_csv(
        path,
        map(build_row, cast(list[dict],
            get_all_candidates_between_days(start, end))),
        headers=[
            "day_of_action",
            "T",
            "is_stock",
            "is_etf",
            "is_warrant",
            "is_unit",
            "is_right",
            "o",
            "h",
            "l",
            "c",
            "v",
        ]
    )


def prepare_csv():
    from src.pathing import get_paths

    path = get_paths()["data"]["outputs"]["daily_rsi_oversold_csv"]

    start, end = get_cache_prepared_date_range_with_leadup_days(0)

    logging.info(f"start: {start}")
    logging.info(f"end: {end}")
    logging.info(
        f"estimated trading days: {len(list(generate_trading_days(start, end)))}")

    prepare_biggest_losers_csv(path, start=start, end=end)
