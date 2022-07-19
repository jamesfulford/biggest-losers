import typing
from datetime import date

from src.scan.utils.indicators import enrich_tickers_with_indicators, extract_from_n_candles_ago
from src.backtest.chronicle.prescanner import build_prescanner_with_empty_candle_getter, with_high_bias_prescan_strategy, with_kwargs
from src.scan.utils.scanners import CandleGetter, ScannerFilter
from src.data.polygon.grouped_aggs import Ticker

LEADUP_PERIOD = 6 * 22


class Candidate(Ticker):
    c_1M: float
    c_3M: float
    c_6M: float
    csi: float


ETFS = {'XLE', 'XLU', 'XLV', 'XLF', 'XLB', 'XLI', 'XLRE', 'XLK', 'XLY', 'XLC'}

# TODO: for added fields, make idempotent (so we can rely just on scanner)


def scanner(provided_tickers: list[Ticker], today: date, _candle_getter: CandleGetter, shallow_scan=False) -> list[Candidate]:

    tickers = provided_tickers  # typing doesn't like re-typing function parameters
    tickers = [t for t in tickers if t['T'] in ETFS]
    tickers = typing.cast(list[Candidate], tickers)

    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "c_1M": extract_from_n_candles_ago('c', 1 * 22),
        "c_3M": extract_from_n_candles_ago('c', 3 * 22),
        "c_6M": extract_from_n_candles_ago('c', 6 * 22),
    }, n=LEADUP_PERIOD + 1))
    for ticker in tickers:
        # average the percent changes together
        ticker["csi"] = (ticker['c_1M'] + ticker['c_3M'] +
                         ticker['c_6M']) / (3 * ticker['c'])

    tickers = sorted(tickers, key=lambda t: t['csi'], reverse=True)

    return tickers


prescanner = build_prescanner_with_empty_candle_getter(
    typing.cast(ScannerFilter, scanner)
)
