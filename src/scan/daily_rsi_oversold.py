from datetime import date

import numpy as np
from talib.abstract import RSI

from src.criteria import is_etf, is_right, is_stock, is_unit, is_warrant
from src.trading_day import generate_trading_days
from src.data.polygon.grouped_aggs import get_cache_prepared_date_range_with_leadup_days, get_last_n_candles
from src.csv_dump import write_csv
from src.data.polygon.grouped_aggs import get_today_grouped_aggs


def _get_rsi(candles: list[dict]):
    inputs = {
        "open": np.array(list(map(lambda c: float(c["o"]), candles))),
        "high": np.array(list(map(lambda c: float(c["h"]), candles))),
        "low": np.array(list(map(lambda c: float(c["l"]), candles))),
        "close": np.array(list(map(lambda c: float(c["c"]), candles))),
        "volume": np.array(list(map(lambda c: float(c["v"]), candles))),
    }
    values = RSI(inputs, timeperiod=14)
    value = float(values[-1])
    return value


#
# _on_day: used for LIVE and BACKTEST
# - all filtering logic should be here
# - all critical indicators should be enriched in here
#
# Some tips:
# - try to filter on OHLCV first before getting daily candles or calculating indicators
def get_all_candidates_on_day(today: date, skip_cache=False):
    today_grouped_aggs = get_today_grouped_aggs(today, skip_cache=skip_cache)
    if not today_grouped_aggs:
        print(f'no data for {today}, cannot fetch candidates')
        return None

    tickers = today_grouped_aggs['results']
    tickers = list(filter(lambda t: t["c"] < 5, tickers))
    tickers = list(filter(lambda t: t["v"] > 300000, tickers))

    # add rsi
    new_tickers = []
    for ticker in tickers:
        daily_candles = get_last_n_candles(today, ticker["T"], n=15)
        if not daily_candles:
            continue
        daily_candles = list(reversed(daily_candles))
        ticker["rsi"] = _get_rsi(daily_candles)

        new_tickers.append(ticker)
    tickers = new_tickers

    tickers = list(filter(lambda t: t["rsi"] < 30, tickers))

    # must be of acceptable type
    new_tickers = []
    for ticker in tickers:
        ticker['is_stock'] = is_stock(ticker['T'], day=today)
        ticker['is_etf'] = is_etf(ticker['T'], day=today)
        ticker['is_warrant'] = is_warrant(ticker['T'], day=today)
        ticker['is_unit'] = is_unit(ticker['T'], day=today)
        ticker['is_right'] = is_right(ticker['T'], day=today)

        if not any((ticker['is_stock'], ticker['is_etf'], ticker['is_warrant'], ticker['is_unit'], ticker['is_right'])):
            continue
        new_tickers.append(ticker)
    tickers = new_tickers

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

        # indicators
        "rsi": candidate["rsi"],
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

    print("start:", start)
    print("end:", end)
    print("estimated trading days:", len(
        list(generate_trading_days(start, end))))

    prepare_biggest_losers_csv(path, start=start, end=end)
