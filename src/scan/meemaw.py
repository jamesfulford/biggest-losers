from typing import cast
from datetime import date

from src.criteria import is_stock
from src.data.yh.stats import get_short_interest
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, from_yesterday_candle
from src.strat.utils.prescanner import build_prescanner_with_empty_candle_getter, with_high_bias_prescan_strategy, with_kwargs
from src.strat.utils.scanners import CandleGetter, ScannerFilter
from src.data.polygon.grouped_aggs import Ticker
from src.data.td.td import get_floats, get_fundamentals

LEADUP_PERIOD = 1


class Candidate(Ticker):
    open_to_close_change: float
    is_stock: bool
    percent_change: float
    c_1d: float
    relative_volume: float
    shares_short: int
    short_interest: float
    float: int


# TODO: for added fields, make idempotent (so we can rely just on scanner)
def scanner(provided_tickers: list[Ticker], today: date, _candle_getter: CandleGetter, shallow_scan=False) -> list[Candidate]:
    max_close_price = 5
    min_volume = 100_000
    min_open_to_close_change = 0
    min_percent_change = 0.05
    min_float, max_float = (1_000_000, 50_000_000)
    min_short_interest = 0.02
    top_n = 1

    tickers = provided_tickers  # typing doesn't like re-typing function parameters

    tickers = list(filter(lambda t: t["c"] < max_close_price, tickers))
    tickers = list(filter(lambda t: t["v"] > min_volume, tickers))

    tickers = cast(list[Candidate], tickers)

    for ticker in tickers:
        ticker["open_to_close_change"] = (
            ticker['c'] - ticker['o']) / ticker['o']
    tickers = list(
        filter(lambda t: t["open_to_close_change"] > min_open_to_close_change, tickers))

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_stock": is_stock,
    }))

    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "c_1d": from_yesterday_candle("c"),
    }, n=LEADUP_PERIOD + 1))
    for ticker in tickers:
        ticker["percent_change"] = (
            ticker["c"] - ticker["c_1d"]) / ticker["c_1d"]
    tickers = list(
        filter(lambda t: t["percent_change"] > min_percent_change, tickers))

    # Low float
    floats = get_floats([t['T'] for t in tickers], today)
    tickers = [t for t in tickers if t['T'] in floats]
    for ticker in tickers:
        ticker["float"] = floats[ticker['T']]
    tickers = list(
        filter(lambda t: t['float'] < max_float and t['float'] > min_float, tickers))

    # High relative volume
    for ticker in tickers:
        ticker['relative_volume'] = ticker['v'] / \
            ticker['float']  # (because >, no divide by zero)
    tickers = list(filter(lambda t: t['relative_volume'], tickers))

    if not shallow_scan:
        # Highest volume first
        tickers.sort(key=lambda t: t['v'], reverse=True)

        # only compute tickers necessary (top_n), less quota usage
        # TODO: achieve this using `yield` by changing Scanners to return iterators?
        new_tickers = []
        for ticker in tickers:
            # Short Interest
            # (done last to save very restricted API call quota)
            short_data = get_short_interest(ticker["T"], today)
            if not short_data:
                continue
            ticker["shares_short"] = short_data["shares_short"]
            ticker["short_interest"] = ticker["shares_short"] / \
                ticker["float"]
            if not (ticker["short_interest"] > min_short_interest):
                continue

            new_tickers.append(ticker)
            if len(new_tickers) >= top_n:
                break
        tickers = new_tickers

    return tickers


prescanner = with_high_bias_prescan_strategy(
    with_kwargs(
        build_prescanner_with_empty_candle_getter(
            # cast: list[Candidate] -> list[Ticker], mypy/Python doesn't understand that `Candidate` is a subtype of `Ticker`
            cast(ScannerFilter, scanner)
        ),
        shallow_scan=True,
    )
)
