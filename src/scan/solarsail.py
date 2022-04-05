from datetime import date
from typing import Callable

from src.data.polygon.asset_class import is_stock
from src.data.finnhub.finnhub import get_candles
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, extract_from_n_candles_ago
from src.scan.utils.rank import rank_candidates_by


LEADUP_PERIOD = 1


def get_all_candidates_on_day(today: date, skip_cache=False):
    tickers = get_all_tickers_on_day(today, skip_cache=skip_cache)
    return filter_all_candidates_on_day(tickers, today)


def filter_all_candidates_on_day(tickers: list, today: date, _candle_getter: Callable = get_candles):
    tickers = list(
        filter(lambda t: t["v"] > 100_000, tickers))

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_stock": is_stock,
    }))
    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "yesterday_close": extract_from_n_candles_ago("c", 1),
    }, n=LEADUP_PERIOD + 1))
    for ticker in tickers:
        percent_change_yesterday = (ticker["c"]-ticker["yesterday_close"]
                                    )/ticker["yesterday_close"]
        ticker["percent_change_yesterday"] = percent_change_yesterday
    tickers = list(
        filter(lambda t: t["percent_change_yesterday"] > 2, tickers))

    tickers = rank_candidates_by(
        tickers, lambda t: -t['percent_change_yesterday'])

    return tickers
