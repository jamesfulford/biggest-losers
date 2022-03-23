from datetime import date
from typing import cast

from src.criteria import is_stock
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.strat.utils.prescanner import build_prescanner_with_empty_candle_getter, with_high_bias_prescan_strategy
from src.strat.utils.scanners import CandleGetter, ScannerFilter
from src.data.polygon.grouped_aggs import Ticker
from src.scan.utils.rank import rank_candidates_by


LEADUP_PERIOD = 0


class Candidate(Ticker):
    percent_change: float


def scanner(provided_tickers: list[Ticker], today: date, _candle_getter: CandleGetter) -> list[Candidate]:
    tickers = cast(list[Candidate], provided_tickers)
    for ticker in tickers:
        ticker["percent_change"] = (ticker['c'] - ticker['o']) / ticker['o']

    tickers = list(filter(lambda t: t["percent_change"] > 2, tickers))

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_stock": is_stock,
    }))

    tickers = rank_candidates_by(
        tickers, lambda t: -t['percent_change'])

    return tickers


prescanner = with_high_bias_prescan_strategy(
    build_prescanner_with_empty_candle_getter(
        # cast: list[Candidate] -> list[Ticker], mypy/Python doesn't understand that `Candidate` is a subtype of `Ticker`
        cast(ScannerFilter, scanner)
    ),
)
