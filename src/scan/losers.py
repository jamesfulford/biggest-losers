from datetime import date
import logging
from typing import Iterable, cast

from src.criteria import is_etf, is_right, is_stock, is_unit, is_warrant
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, from_yesterday_candle
from src.scan.utils.rank import rank_candidates_by
from src.trading_day import generate_trading_days
from src.data.polygon.grouped_aggs import Ticker, get_cache_prepared_date_range_with_leadup_days
from src.csv_dump import write_csv


class Candidate(Ticker):
    is_etf: bool
    is_right: bool
    is_stock: bool
    is_unit: bool
    is_warrant: bool

    yesterday_c: float

    percent_change: float


class CandidateWithDayOfAction(Candidate):
    day_of_action: date


#
# _on_day: used for LIVE and BACKTEST
# - all filtering logic should be here
# - all critical indicators should be enriched in here
#
# Some tips:
# - try to filter on OHLCV first before getting daily candles or calculating indicators
def get_all_candidates_on_day(today: date, skip_cache=False) -> list[Candidate]:
    tickers = get_all_tickers_on_day(today, skip_cache=skip_cache)
    tickers = list(filter(lambda t: t["v"] > 100000, tickers))

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_etf": is_etf,
        "is_right": is_right,
        "is_stock": is_stock,
        "is_unit": is_unit,
        "is_warrant": is_warrant,
    }))

    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "yesterday_c": from_yesterday_candle("c"),
    }, n=2))

    tickers = cast(list[Candidate], tickers)

    for ticker in tickers:
        ticker['percent_change'] = (
            ticker['c'] - ticker['yesterday_c']) / ticker['yesterday_c']

    tickers = list(filter(lambda t: t["percent_change"] < -.2, tickers))

    tickers = rank_candidates_by(tickers, lambda t: t['percent_change'])

    return tickers


def get_all_candidates_between_days(start: date, end: date) -> Iterable[CandidateWithDayOfAction]:
    for day in generate_trading_days(start, end):
        for candidate in get_all_candidates_on_day(day) or []:
            new_candidate = cast(CandidateWithDayOfAction, candidate)
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

        # rank
        "rank": candidate["rank"],

        # indicators
        "vw": candidate["vw"],
        "yesterday_c": candidate["yesterday_c"],
        "percent_change": candidate["percent_change"],
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

    path = get_paths()["data"]["outputs"]["losers_csv"]

    start, end = get_cache_prepared_date_range_with_leadup_days(0)

    logging.info(f"start: {start}")
    logging.info(f"end: {end}")
    logging.info(
        f"estimated trading days: {len(list(generate_trading_days(start, end)))}")

    prepare_biggest_losers_csv(path, start=start, end=end)
