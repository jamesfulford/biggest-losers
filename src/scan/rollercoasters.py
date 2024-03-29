from datetime import date
import logging

from src.data.polygon.asset_class import is_etf, is_right, is_stock, is_unit, is_warrant
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, extract_from_n_candles_ago
from src.trading_day import generate_trading_days
from src.data.polygon.grouped_aggs import get_cache_prepared_date_range_with_leadup_days
from src.outputs.csv_dump import write_csv
from src.scan.utils.rank import rank_candidates_by


def get_all_candidates_on_day(today: date, skip_cache=False):
    tickers = get_all_tickers_on_day(today, skip_cache=skip_cache)
    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        # how many days ago for percentage change
        "days_ago_close": extract_from_n_candles_ago("c", 6),
    }, n=6))
    for ticker in tickers:
        percent_change_days_ago = (ticker["c"]-ticker["days_ago_close"]
                                   )/ticker["days_ago_close"]
        ticker["percent_change_days_ago"] = percent_change_days_ago
    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_stock": is_stock,
    }))
    tickers = list(
        filter(lambda t: t["percent_change_days_ago"] > .1, tickers))
    tickers = rank_candidates_by(
        tickers, lambda t: -t['percent_change_days_ago'])
    return tickers


def get_all_candidates_between_days(start: date, end: date):
    for day in generate_trading_days(start, end):
        for candidate in get_all_candidates_on_day(day) or []:
            candidate["day_of_action"] = day
            yield candidate


def build_row(candidate: dict):
    return {
        "day_of_action": candidate['day_of_action'],
        # ticker insights
        "T": candidate['T'],
        "is_stock": candidate['is_stock'],

        # day_of_action stats
        "o": candidate["o"],
        "h": candidate["h"],
        "l": candidate["l"],
        "c": candidate["c"],
        "v": candidate["v"],
        "n": candidate["n"],

        # indicators
        "percent_change_days_ago": candidate["percent_change_days_ago"],
        "vw": candidate["vw"],
    }


def prepare_biggest_losers_csv(path: str, start: date, end: date):
    write_csv(
        path,
        map(build_row, get_all_candidates_between_days(start, end)),
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
            "percent_change_days_ago",
        ]
    )


def prepare_csv():
    from src.outputs.pathing import get_paths

    path = get_paths()["data"]["outputs"]["rollercoasters_csv"]

    start, end = get_cache_prepared_date_range_with_leadup_days(0)

    logging.info(f"start: {start}")
    logging.info(f"end: {end}")
    logging.info(
        f"estimated trading days: {len(list(generate_trading_days(start, end)))}")

    prepare_biggest_losers_csv(path, start=start, end=end)
