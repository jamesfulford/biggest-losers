from datetime import date
from typing import cast

from src.data.polygon.asset_class import is_etf, is_stock
from src.data.polygon.grouped_aggs import Ticker
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, from_yesterday_candle
from src.scan.utils.rank import rank_candidates_by
from src.backtest.chronicle.prescanner import build_prescanner_with_empty_candle_getter, with_high_bias_prescan_strategy
from src.scan.utils.scanners import CandleGetter, ScannerFilter


LEADUP_PERIOD = 1


class Candidate(Ticker):
    percent_change: float
    yesterday_c: float


def scanner(provided_tickers: list[Ticker], today: date, _candle_getter: CandleGetter) -> list[Candidate]:
    tickers = cast(list[Candidate], provided_tickers)
    tickers = list(filter(lambda t: t["v"] > 100000, tickers))

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_etf": is_etf,
        "is_stock": is_stock,
    }))

    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "yesterday_c": from_yesterday_candle("c"),
    }, n=LEADUP_PERIOD + 1))

    for ticker in tickers:
        ticker['percent_change'] = (
            ticker['c'] - ticker['yesterday_c']) / ticker['yesterday_c']

    tickers = list(filter(lambda t: t["percent_change"] > .5, tickers))

    tickers = rank_candidates_by(
        tickers, lambda t: -t['percent_change'])

    return tickers


prescanner = with_high_bias_prescan_strategy(
    build_prescanner_with_empty_candle_getter(
        # cast: list[Candidate] -> list[Ticker], mypy/Python doesn't understand that `Candidate` is a subtype of `Ticker`
        cast(ScannerFilter, scanner)
    ),
)
