from multiprocessing import Pool
import os
from typing import Callable
import ta
import pandas as pd
from datetime import date, datetime, time, timedelta
import logging
from src import jsonl_dump

from src.criteria import is_stock
from src.data.finnhub.finnhub import get_candles
from src.data.yh.stats import get_short_interest
from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.scan.utils.asset_class import enrich_tickers_with_asset_class
from src.scan.utils.indicators import enrich_tickers_with_indicators, from_yesterday_candle
from src.trading_day import MARKET_TIMEZONE, generate_trading_days
from src.data.polygon.grouped_aggs import get_cache_prepared_date_range_with_leadup_days
from src.data.finnhub.finnhub import get_candles


#
# _on_day: used for LIVE and BACKTEST
# - all filtering logic should be here
# - all critical indicators should be enriched in here
#
# Some tips:
# - try to filter on OHLCV first before getting daily candles or calculating indicators

from src.data.td.td import get_fundamentals


def get_all_candidates_on_day(today: date, skip_cache=False):
    tickers = get_all_tickers_on_day(today, skip_cache=skip_cache)
    return filter_candidates_on_day(tickers, today, shallow_scan=not skip_cache)


def get_vwap(candles):
    highs = pd.Series(list(map(lambda c: float(c["high"]), candles)))
    lows = pd.Series(list(map(lambda c: float(c["low"]), candles)))
    closes = pd.Series(list(map(lambda c: float(c["close"]), candles)))
    volumes = pd.Series(list(map(lambda c: float(c["volume"]), candles)))
    values = ta.volume.volume_weighted_average_price(
        highs, lows, closes, volumes)
    return values.tolist()[-1]


def filter_candidates_on_day(tickers: list, today: date, candle_getter: Callable = get_candles, shallow_scan=False):
    max_close_price = 5
    min_volume = 100_000
    min_open_to_close_change = 0
    min_percent_change = 0.05
    min_float, max_float = (1_000_000, 50_000_000)
    min_short_interest = 0.02
    top_n = 1

    tickers = list(filter(lambda t: t["c"] < max_close_price, tickers))
    tickers = list(filter(lambda t: t["v"] > min_volume, tickers))

    for ticker in tickers:
        ticker["open_to_close_change"] = (
            ticker['c'] - ticker['o']) / ticker['o']
    tickers = list(
        filter(lambda t: t["open_to_close_change"] > min_open_to_close_change, tickers))

    tickers = list(enrich_tickers_with_asset_class(today, tickers, {
        "is_stock": is_stock,
    }))

    tickers = list(enrich_tickers_with_indicators(today, tickers, {
        "c-1d": from_yesterday_candle("c"),
        "v-1d": from_yesterday_candle("v"),
    }, n=2))
    for ticker in tickers:
        ticker["percent_change"] = (
            ticker["c"] - ticker["c-1d"]) / ticker["c-1d"]
    tickers = list(
        filter(lambda t: t["percent_change"] > min_percent_change, tickers))

    # Low float
    # TODO: instruct `get_fundamentals` to check cache for data nearest `day`
    fundamentals = get_fundamentals(list(map(lambda t: t["T"], tickers)))
    tickers = list(filter(lambda t: t["T"] in fundamentals, tickers))
    for ticker in tickers:
        ticker['float'] = fundamentals[ticker['T']]['shares']['float']
    tickers = list(
        filter(lambda t: t['float'] < max_float and t['float'] > min_float, tickers))

    # High relative volume
    for ticker in tickers:
        ticker['relative_volume'] = ticker['v'] / \
            ticker['float']  # (because >, no divide by zero)
    tickers = list(filter(lambda t: t['relative_volume'], tickers))

    if not shallow_scan:
        # Above the VWAP on 1m chart
        for ticker in tickers:
            ticker['vwap_1m'] = get_vwap(
                candle_getter(ticker["T"], "1", today, today))
        tickers = list(filter(lambda t: t['c'] > t['vwap_1m'], tickers))

        # Highest volume first
        tickers.sort(key=lambda t: t['v'], reverse=True)

        # Short Interest
        # (done last to save very restricted API call quota)
        new_tickers = []
        for ticker in tickers:
            short_data = get_short_interest(ticker["T"], today)
            if short_data:
                ticker["shares_short"] = short_data["shares_short"]
                ticker["short_interest"] = ticker["shares_short"] / \
                    ticker["float"]
                if ticker["short_interest"] > min_short_interest:
                    new_tickers.append(ticker)
                    if len(new_tickers) >= top_n:
                        break
        tickers = new_tickers

    return tickers


def main():
    output_path = '/tmp/meemaw_candidates.jsonl'
    try:
        os.remove(output_path)
    except:
        pass

    start, end = get_cache_prepared_date_range_with_leadup_days(0)
    # earliest we can get short interest data for
    start = max(start, date(2022, 1, 14))
    end = min(end, date(2022, 3, 4))  # asap

    logging.info(f"start: {start}")
    logging.info(f"end: {end}")
    logging.info(
        f"estimated trading days: {len(list(generate_trading_days(start, end)))}")

    for day in generate_trading_days(start, end):
        backtest_on_day(day, output_path)


def backtest_on_day(day: date, output_path: str):
    #
    # Pre-scan pass on daily candles to slim down the number of candidates
    #
    tickers = get_all_tickers_on_day(day, skip_cache=False)
    # NOTE: mangling daily candles so close is high
    # so the %up filter won't lock out if the price was high at some point
    for ticker in tickers:
        ticker['_c'] = ticker['c']
        ticker['c'] = ticker['h']
    tickers = filter_candidates_on_day(tickers, day, shallow_scan=True)
    logging.info(f"processing {len(tickers)} tickers for {day}")

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
    while current_time.time() < time(16, 0):
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
        if current_time.time() > time(9, 30):
            returned_tickers = filter_candidates_on_day(
                daily_candles, day, lambda s, t, st, en: symbol_to_current_candles[s])

            if returned_tickers:
                jsonl_dump.append_jsonl(output_path, [{
                    "now": current_time,
                    "ticker": ticker,
                } for ticker in returned_tickers])

# 1. pre-scan to find candidates we *might* be interested in (float, high enough volume by EOD, 'h' is high enough)
# 2. get 1m candles for each candidate on each day
# 3. build partial D candles (c=current close, o=day's open, h=day's high so far, l=day's low so far, v=cumulative sum of volume)
# 4. feed partial D candles to filter_candidates_on_day
# 5. print it out
