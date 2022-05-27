import datetime
import typing
from src.backtest.chronicle.prescanner import build_prescanner_with_empty_candle_getter, with_high_bias_prescan_strategy

from src.data.polygon.asset_class import is_stock
from src.data.polygon.grouped_aggs import Ticker
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.rank import rank_candidates_by
from src.scan.utils.scanners import CandleGetter, ScannerFilter

LEADUP_PERIOD = 0


class Candidate(Ticker):
    is_stock: bool
    open_to_close_change: float


def scanner(provided_tickers: list[Ticker], today: datetime.date, _candle_getter: CandleGetter) -> list[Candidate]:
    tickers = typing.cast(list[Candidate], provided_tickers)
    tickers = list(
        filter(lambda t: t["v"] > 100_000, tickers))

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_stock": is_stock,
    }))
    for ticker in tickers:
        ticker['open_to_close_change'] = (
            ticker['c'] - ticker['o']) / ticker['o']
    tickers = list(
        filter(lambda t: t["open_to_close_change"] >= 0.5, tickers))

    tickers = rank_candidates_by(
        tickers, lambda t: -t['open_to_close_change'])

    return tickers


prescanner = with_high_bias_prescan_strategy(
    build_prescanner_with_empty_candle_getter(
        # cast: list[Candidate] -> list[Ticker], mypy/Python doesn't understand that `Candidate` is a subtype of `Ticker`
        typing.cast(ScannerFilter, scanner)
    ),
)
