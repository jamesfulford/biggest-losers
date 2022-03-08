from copy import deepcopy
from datetime import date, datetime, time, timedelta
import logging
from typing import Callable

from src.criteria import is_stock
from src.data.finnhub.finnhub import get_candles
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, extract_from_n_candles_ago
from src.trading_day import MARKET_TIMEZONE, generate_trading_days
from src.data.polygon.grouped_aggs import get_cache_prepared_date_range_with_leadup_days
from src.scan.utils.rank import rank_candidates_by


def get_all_candidates_on_day(today: date, skip_cache=False):
    tickers = get_all_tickers_on_day(today, skip_cache=skip_cache)
    return filter_all_candidates_on_day(tickers, today)


def filter_all_candidates_on_day(tickers: list, today: date, _candle_getter: Callable = None):
    tickers = list(
        filter(lambda t: t["v"] > 100_000, tickers))

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_stock": is_stock,
    }))
    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "yesterday_close": extract_from_n_candles_ago("c", 1),
    }, n=2))
    for ticker in tickers:
        percent_change_yesterday = (ticker["c"]-ticker["yesterday_close"]
                                    )/ticker["yesterday_close"]
        ticker["percent_change_yesterday"] = percent_change_yesterday
    tickers = list(
        filter(lambda t: t["percent_change_yesterday"] > 2, tickers))

    tickers = rank_candidates_by(
        tickers, lambda t: -t['percent_change_yesterday'])

    return tickers


def main():
    start, end = get_cache_prepared_date_range_with_leadup_days(0)

    logging.info(f"start: {start}")
    logging.info(f"end: {end}")
    logging.info(
        f"estimated trading days: {len(list(generate_trading_days(start, end)))}")

    for day in generate_trading_days(start, end):
        for candidate in backtest_on_day(day, filter_all_candidates_on_day,
                                         pre_scanner=filter_all_candidates_on_day):
            print(day, candidate['symbol'], candidate['true_daily_candle']['c']/candidate['simulated_daily_candle']
                  ['c'])


def backtest_on_day(day: date, scanner: Callable, pre_scanner: Callable, end_time=time(10, 0), start_invoking_time=time(10, 0)):
    tickers = get_all_tickers_on_day(day, skip_cache=False)
    #
    # Pre-scan pass on daily candles to slim down the number of candidates
    #

    # mangling daily candles so close is high
    # so the %up filter won't lock out if the price was high at some point
    mangled_tickers = deepcopy(tickers)
    for ticker in mangled_tickers:
        ticker['_c'] = ticker['c']
        ticker['c'] = ticker['h']
    mangled_tickers = pre_scanner(mangled_tickers, day)
    if not mangled_tickers:
        return
    logging.info(f"processing {len(mangled_tickers)} tickers for {day}")
    prescan_passed_symbols = set(map(lambda t: t['T'], mangled_tickers))
    tickers = list(
        filter(lambda t: t['T'] in prescan_passed_symbols, tickers))

    #
    # In-depth 1m candles scan
    #

    symbol_to_candles = {}
    for ticker in tickers:
        symbol = ticker["T"]
        candles = get_candles(symbol, "1", day, day)
        if not candles:
            logging.warn(f"no candles for {symbol} on {day}, {candles=}")
            continue
        symbol_to_candles[symbol] = candles
    tickers = list(filter(lambda t: t["T"] in symbol_to_candles, tickers))

    # simulate intraday daily candles as they develop minute-by-minute
    # (pay attention to how we call filter_candidates_on_day)
    current_time = datetime(day.year, day.month,
                            day.day, 4, 0).astimezone(MARKET_TIMEZONE)
    while current_time.time() < end_time:
        current_time += timedelta(minutes=1)

        # build map of symbol to candles visible at current_time
        symbol_to_current_candles = {}
        for symbol, candles in symbol_to_candles.items():
            symbol_to_current_candles[symbol] = list(
                filter(lambda c: c["datetime"] < current_time, candles))

        # build simulated intraday candles
        daily_candles = []
        for ticker in tickers:
            symbol = ticker['T']
            # respects current time
            current_candles = symbol_to_current_candles[symbol]
            d_candle = {
                "T": symbol,
                'v': 0,
                "__future_daily_candle": ticker
            }
            for candle in current_candles:
                # TODO: how do daily candles in polygon API work before market open?
                # TODO: are candles start-of-minute or end-of-minute? (>= or >)
                if candle['datetime'].time() >= time(9, 30):
                    if 'o' not in d_candle:
                        d_candle['o'] = candle['open']

                    d_candle['h'] = max(
                        d_candle.get('h', 0), candle['high'])
                    d_candle['l'] = min(
                        d_candle.get('l', 1e9), candle['low'])

                d_candle['c'] = candle['close']
                d_candle['v'] += candle['volume']

            if current_candles:  # at least 1 candle occurred
                daily_candles.append(d_candle)

        # filter candidates, record results
        if current_time.time() >= start_invoking_time:
            returned_tickers = scanner(
                daily_candles, day, lambda s, t, st, en: symbol_to_current_candles[s])

            if returned_tickers:
                yield from [{
                    "now": current_time,
                    "symbol": ticker['T'],
                    "simulated_daily_candle": ticker,  # 10am candle
                    # 4:00 close candle
                    "true_daily_candle": ticker["__future_daily_candle"],
                } for ticker in returned_tickers]
