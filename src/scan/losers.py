import datetime
import logging
import typing

from src.data.polygon.asset_class import is_etf, is_right, is_stock, is_unit, is_warrant
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, from_yesterday_candle
from src.scan.utils.rank import rank_candidates_by

from src.backtest.chronicle.prescanner import build_prescanner_with_empty_candle_getter, with_high_bias_prescan_strategy
from src.scan.utils.scanners import CandleGetter, ScannerFilter
from src.data.polygon.grouped_aggs import Ticker


LEADUP_PERIOD = 1


class Candidate(Ticker):
    is_stock: bool
    # is_etf: bool
    # is_right: bool
    # is_unit: bool
    # is_warrant: bool

    yesterday_c: float

    percent_change: float
    day_of_action: datetime.date


def scanner(provided_tickers: list[Ticker], today: datetime.date, _candle_getter) -> list[Candidate]:
    tickers = typing.cast(list[Candidate], provided_tickers)
    logging.debug(f'Starting basic filters... {len(tickers)}')
    tickers = list(filter(lambda t: t["v"] > 100000, tickers))
    tickers = list(filter(lambda t: t["c"] > 3, tickers))
    tickers = list(filter(lambda t: t["c"] < 50, tickers))

    logging.debug(f'Starting is_stock filter... {len(tickers)}')
    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_stock": is_stock,
        # "is_etf": is_etf,
        # "is_right": is_right,
        # "is_unit": is_unit,
        # "is_warrant": is_warrant,
    }))
    tickers = list(filter(lambda t: t['is_stock'], tickers))

    logging.debug(f'Starting yesterday_c lookup... {len(tickers)}')
    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "yesterday_c": from_yesterday_candle("c"),
    }, n=2))

    logging.debug(f'Starting percent_change filter... {len(tickers)}')
    for ticker in tickers:
        ticker["percent_change"] = (
            ticker['c'] - ticker['yesterday_c']) / ticker['yesterday_c']
    tickers = list(filter(lambda t: t['percent_change'] < -.5, tickers))

    logging.debug(f'Ranking by percent_change... {len(tickers)}')
    tickers = rank_candidates_by(
        tickers, lambda t: -t['percent_change'])

    return tickers


prescanner = with_high_bias_prescan_strategy(build_prescanner_with_empty_candle_getter(
    # cast: list[Candidate] -> list[Ticker], mypy/Python doesn't understand that `Candidate` is a subtype of `Ticker`
    typing.cast(ScannerFilter, scanner)
))
