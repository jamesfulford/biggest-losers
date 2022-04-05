from datetime import date
from typing import cast

from src.data.polygon.asset_class import is_etf, is_stock
from src.data.polygon.grouped_aggs import Ticker
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, from_yesterday_candle
from src.scan.utils.rank import rank_candidates_by
from src.strat.utils.prescanner import build_prescanner_with_empty_candle_getter
from src.strat.utils.scanners import CandleGetter, ScannerFilter


LEADUP_PERIOD = 1


class Candidate(Ticker):
    yesterday_v: float
    volume_percent_change: float


def scanner(provided_tickers: list[Ticker], today: date, _candle_getter: CandleGetter) -> list[Candidate]:
    """
    NOTE: this scanner would be hard to use intraday because volume is not complete
    """
    tickers = cast(list[Candidate], provided_tickers)
    tickers = list(filter(lambda t: t["v"] > 100_000, tickers))

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_etf": is_etf,
        "is_stock": is_stock,
    }))

    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "yesterday_v": from_yesterday_candle("v"),
    }, n=LEADUP_PERIOD + 1))

    tickers = list(filter(lambda t: t["yesterday_v"] > 100_000, tickers))

    for ticker in tickers:
        ticker['volume_percent_change'] = (
            ticker['v'] - ticker['yesterday_v']) / ticker['yesterday_v']

    tickers = list(filter(lambda t: t["volume_percent_change"] > .5, tickers))

    tickers = rank_candidates_by(
        tickers, lambda t: -t['volume_percent_change'])

    return tickers


prescanner = build_prescanner_with_empty_candle_getter(
    # cast: list[Candidate] -> list[Ticker], mypy/Python doesn't understand that `Candidate` is a subtype of `Ticker`
    cast(ScannerFilter, scanner)
)
