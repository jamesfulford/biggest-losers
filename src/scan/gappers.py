from datetime import date

from src.criteria import is_etf, is_right, is_stock, is_unit, is_warrant
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, from_yesterday_candle
from src.scan.utils.rank import rank_candidates_by
from src.trading_day import generate_trading_days
from src.data.polygon.grouped_aggs import get_cache_prepared_date_range_with_leadup_days
from src.csv_dump import write_csv


#
# _on_day: used for LIVE and BACKTEST
# - all filtering logic should be here
# - all critical indicators should be enriched in here
#
# Some tips:
# - try to filter on OHLCV first before getting daily candles or calculating indicators
def get_all_candidates_on_day(today: date, skip_cache=False):
    tickers = get_all_tickers_on_day(today, skip_cache=skip_cache)

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_etf": is_etf,
        "is_right": is_right,
        "is_stock": is_stock,
        "is_unit": is_unit,
        "is_warrant": is_warrant,
    }))

    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "yesterday_c": from_yesterday_candle("c"),
        "yesterday_v": from_yesterday_candle("v"),
    }, n=2))

    for ticker in tickers:
        ticker["gap"] = (ticker["o"] - ticker["yesterday_c"]
                         ) / ticker["yesterday_c"]

    tickers = list(filter(lambda t: t["gap"] > .5, tickers))

    tickers = rank_candidates_by(tickers, lambda t: -t["gap"])

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
        "gap": candidate["gap"],
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

    path = get_paths()["data"]["outputs"]["gappers_csv"]

    start, end = get_cache_prepared_date_range_with_leadup_days(0)
    start = max(start, date(2021, 1, 1))  # TODO: undo
    end = min(end, date(2021, 12, 31))  # TODO: undo

    print("start:", start)
    print("end:", end)
    print("estimated trading days:", len(
        list(generate_trading_days(start, end))))

    prepare_biggest_losers_csv(path, start=start, end=end)
