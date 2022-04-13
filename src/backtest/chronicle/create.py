import argparse
from copy import deepcopy
from datetime import date, datetime, time, timedelta
import logging
import os
from typing import Iterable, Optional, cast
from src.outputs import jsonl_dump
from src.backtest.chronicle.read import HistoricalChronicleEntry, get_scanner_backtest_chronicle_path
from src.data.finnhub.finnhub import get_candles
from src.data.types.candles import CandleIntraday
from src.data.polygon.grouped_aggs import Ticker, get_cache_entry_refresh_time, get_cache_prepared_date_range_with_leadup_days
from src.scripts.helpers.parse_period import add_range_args, interpret_args

from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.scan.utils.scanners import PrescannerFilter, ScannerFilter, get_leadup_period, get_prescanner_filter, get_scanner_filter
from src.trading_day import MARKET_TIMEZONE, generate_trading_days


# TODO: to parallelize, need to synchronize cache read/writes by cache key to avoid potential data corruption issues
# (or demand that parallelization only be by day, then only sync when cross day boundaries? case a: float/short interest (sync). case b: yesterday's 1m candles (no sync). case c: monday of this week's 1m candles (sync))
def build_daily_candle_from_1m_candles(symbol: str, candles: list[CandleIntraday]) -> Optional[Ticker]:
    if not candles:
        return None

    opening_candle = next(
        filter(lambda c: c["datetime"].time() >= time(9, 30), candles), None)
    if not opening_candle:
        return None

    high = 0
    low = 1e9
    volume = 0
    close = opening_candle['close']
    o = opening_candle['open']
    for candle in candles:
        if candle['datetime'].time() >= time(9, 30):
            if not o:
                o = candle['open']

            high = max(high, candle['high'])
            low = min(low, candle['low'])

        close = candle['close']

        # https://forum.alpaca.markets/t/unstable-minute-bar-real-time-data-2022-03-30-googl/8996/9
        # > Volume is a dilemma. Most trades, including most of those excluded above, are included in volume calculations.
        # > If there is a bar, then the trades are included in volume. However, if there isn’t a bar then the volume for
        # > any ‘excluded’ trades doesn’t get counted (ie there isn’t a bar to attach it to).
        # > **Summing the bars for the day will therefore generally sum to less than the volume for the day.**
        # > The ‘best practice’ to getting the current volume for the day is to fetch a snapshot and use the daily_bar.volume which is returned.
        # > That will be the actual daily volume up to the current time.

        # This will *underestimate* volume. This is a consequence of how candles work and how some trades are excluded from candles.

        volume += candle['volume']

    dcandle: Ticker = {
        "T": symbol,
        "o": o,
        "h": high,
        "l": low,
        "c": close,
        "v": int(volume),

        # obvously wrong values so that nobody uses them
        # TODO: implement VWAP field based on 1m candles (then correct README.md)
        "vw": 0,
        "n": 0,
    }
    return dcandle


def get_1m_candles_by_symbol(symbols: list[str], day: date) -> dict[str, list[CandleIntraday]]:
    symbol_to_candles: dict[str, list[CandleIntraday]] = {}
    for symbol in symbols:
        candles = get_candles(symbol, "1", day, day)
        if not candles:
            logging.warn(f"no candles for {symbol} on {day}, {candles=}")
            continue
        symbol_to_candles[symbol] = cast(list[CandleIntraday], candles)
    return symbol_to_candles


def backtest_on_day(day: date, scanner_filter: ScannerFilter, prescanner_filter: PrescannerFilter,
                    end_time=time(16, 0)
                    ) -> Iterable[HistoricalChronicleEntry]:
    tickers = get_all_tickers_on_day(day)

    # Pre-scan pass on daily candles to slim down the number of candidates
    # (assume that prescanner will mutate tickers, so we need to copy)
    mangled_tickers = deepcopy(tickers)
    mangled_tickers = prescanner_filter(mangled_tickers, day)

    prescan_passed_symbols = set(map(lambda t: t['T'], mangled_tickers))
    tickers = list(
        filter(lambda t: t['T'] in prescan_passed_symbols, tickers))
    if not tickers:
        return

    logging.info(
        f"processing {len(tickers)} tickers for {day}")

    symbol_to_true_ticker = {t['T']: t for t in tickers}

    # In-depth 1m candles scan
    symbol_to_candles = get_1m_candles_by_symbol(
        [t['T'] for t in tickers], day)
    tickers = list(filter(lambda t: t["T"] in symbol_to_candles, tickers))

    # TODO: 1m candles from finnhub are unadjusted, but some data used by scanners are! (e.g. previous day candle) How to handle this?
    # MAYBE: check ticker (in tickers), compare to 9:30 1m candle, use that ratio to adjust finnhub as we go?
    for ticker in tickers:
        adjusted_open = ticker['o']
        opening_unadjusted_candle = next(filter(lambda c: c['datetime'].time() >= time(
            9, 30), symbol_to_candles[ticker['T']]))
        unadjusted_open = opening_unadjusted_candle['open']

        open_price_ratio = (adjusted_open / unadjusted_open)
        if open_price_ratio > 1.1 or open_price_ratio < 0.9:
            # obvious stock split
            logging.warn(
                f"{day} {ticker['T']} mismatch open price! {adjusted_open=} {unadjusted_open=} ratio={open_price_ratio} TODO: implement candle adjustment")

    # TODO: pass in a time iterator so we can control every 5m, 30m, once daily, etc.
    # NOTE: while we could simulate pre-market and after-market, we can't scan it live

    # simulate intraday daily candles as they develop minute-by-minute
    # (pay attention to how we call scanner)
    current_time = datetime(day.year, day.month,
                            day.day, 9, 29).astimezone(MARKET_TIMEZONE)
    while current_time.time() < end_time:
        current_time += timedelta(minutes=1)

        # build map of symbol to candles visible at current_time
        symbol_to_current_candles = {}
        for symbol, candles in symbol_to_candles.items():
            symbol_to_current_candles[symbol] = list(
                filter(lambda c: c["datetime"] < current_time, candles))

        # build simulated intraday candles
        daily_candles = [build_daily_candle_from_1m_candles(t['T'],
                                                            symbol_to_current_candles[t['T']]) for t in tickers if symbol_to_current_candles[t['T']]]
        daily_candles = [d for d in daily_candles if d]

        # filter candidates, record results
        returned_tickers = scanner_filter(
            daily_candles,
            day,
            lambda s, t, st, en: symbol_to_current_candles[s]
        )

        for ticker in returned_tickers:
            entry: HistoricalChronicleEntry = {
                "now": current_time,
                "ticker": ticker,
                "true_ticker": symbol_to_true_ticker[ticker['T']]
            }
            yield entry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=str)
    parser = add_range_args(parser, required=False)
    args = parser.parse_args()

    scanner_name = args.scanner
    scanner_filter = get_scanner_filter(scanner_name)
    prescanner_filter = get_prescanner_filter(scanner_name)
    leadup_period = get_leadup_period(scanner_name)

    cache_start, cache_end = get_cache_prepared_date_range_with_leadup_days(
        leadup_period)
    logging.info(f"{cache_start=} {cache_end=}")

    try:
        start, end = interpret_args(args)
    except:
        logging.info("Did not parse range, using cache range...")
        start = cache_start
        end = cache_end

    # stay within cache range
    start = max(start, cache_start)
    end = min(end, cache_end)

    logging.info(f"{start=} {end=}")

    logging.info(
        f"estimated trading days: {len(list(generate_trading_days(start, end)))}")
    cache_built_day = get_cache_entry_refresh_time(end).date()
    logging.info(f"cache built time: {cache_built_day}")

    output_path = get_scanner_backtest_chronicle_path(
        scanner_name, cache_built_day)
    try:
        os.makedirs(os.path.dirname(output_path))
    except:
        pass
    try:
        os.remove(output_path)
    except:
        pass

    logging.info("Building chronicle...")

    for day in generate_trading_days(start, end):
        candidates = backtest_on_day(
            day, scanner_filter, prescanner_filter=prescanner_filter)
        jsonl_dump.append_jsonl(output_path, cast(Iterable[dict], candidates))

    logging.info("Done building chronicle.")
