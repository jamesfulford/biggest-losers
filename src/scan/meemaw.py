from datetime import date
import logging

from src.criteria import is_etf, is_right, is_stock, is_unit, is_warrant
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, from_yesterday_candle, use_indicator
from src.trading_day import generate_trading_days
from src.data.polygon.grouped_aggs import get_cache_prepared_date_range_with_leadup_days
from src.csv_dump import write_csv

from talib.abstract import RSI

#
# _on_day: used for LIVE and BACKTEST
# - all filtering logic should be here
# - all critical indicators should be enriched in here
#
# Some tips:
# - try to filter on OHLCV first before getting daily candles or calculating indicators

from src.data.td.td import get_fundamentals


def get_all_candidates_on_day(today: date, skip_cache=False):
    tickers = get_all_tickers_on_day(today, skip_cache=skip_cache)
    tickers = list(filter(lambda t: t["c"] < 5, tickers))
    tickers = list(filter(lambda t: t["v"] > 100_000, tickers))

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_stock": is_stock,
    }))

    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "c-1d": from_yesterday_candle("c"),
        "v-1d": from_yesterday_candle("v"),
    }, n=2))

    for ticker in tickers:
        # TODO: in backtest, use 'h', when live use 'c'?
        ticker["percent_change"] = (
            ticker["c"] - ticker["c-1d"]) / ticker["c-1d"]
    tickers = list(filter(lambda t: t["percent_change"] > 0.05, tickers))

    # TODO: how to backtest this? Do not have historical floats...
    fundamentals = get_fundamentals(list(map(lambda t: t["T"], tickers)))
    tickers = list(filter(lambda t: t["T"] in fundamentals, tickers))
    for ticker in tickers:
        ticker['float'] = fundamentals[ticker['T']]['shares']['float']
    tickers = list(
        filter(lambda t: t['float'] < 50_000_000 and t['float'] > 1_000_000, tickers))

    tickers.sort(key=lambda t: t['v']/t['float'], reverse=True)

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

        # day_of_action stats
        "o": candidate["o"],
        "h": candidate["h"],
        "l": candidate["l"],
        "c": candidate["c"],
        "v": candidate["v"],
        "n": candidate["n"],

        # indicators
        "float": candidate["float"],
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
        ]
    )


def prepare_csv():
    from src.pathing import get_paths

    path = get_paths()["data"]["outputs"]["daily_rsi_oversold_csv"]

    start, end = get_cache_prepared_date_range_with_leadup_days(0)
    start = max(start, date(2021, 1, 1))  # TODO: undo
    end = min(end, date(2021, 12, 31))  # TODO: undo

    logging.info(f"start: {start}")
    logging.info(f"end: {end}")
    logging.info(
        f"estimated trading days: {len(list(generate_trading_days(start, end)))}")

    prepare_biggest_losers_csv(path, start=start, end=end)