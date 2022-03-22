from copy import deepcopy
from datetime import date, datetime, time, timedelta
import logging
import os
from typing import Callable, Iterable, Optional, TypedDict, cast, get_args
from src import jsonl_dump
from src.data.finnhub.finnhub import CandleIntraday, get_candles
from src.data.polygon.grouped_aggs import Ticker, TickerLike, get_cache_prepared_date_range_with_leadup_days

from src.scan.utils.all_tickers_on_day import get_all_tickers_on_day
from src.strat.utils.scanners import CandleGetter, ScannerFilter, get_leadup_period, get_scanner_filter
from src.trading_day import MARKET_TIMEZONE, generate_trading_days


class ChronicleEntry(TypedDict):
    now: datetime
    ticker: Ticker


class HistoricalChronicleEntry(ChronicleEntry):
    true_ticker: Ticker


def build_daily_candle_from_1m_candles(symbol: str, candles: list[CandleIntraday]) -> Optional[Ticker]:
    if not candles:
        return None

    high = 0
    low = 1e9
    volume = 0
    close = candles[0]['close']
    o = None
    for candle in candles:
        # TODO: how do daily candles in polygon API work before market open? (adjust dcandle below)
        # TODO: are candles start-of-minute or end-of-minute? (>= or >)
        if candle['datetime'].time() >= time(9, 30):
            if not o:
                o = candle['open']

            high = max(high, candle['high'])
            low = min(low, candle['low'])

        close = candle['close']
        volume += candle['volume']

    dcandle: Ticker = {
        "T": symbol,
        "o": o if o else candles[0]['open'],
        "h": high,
        "l": low,
        "c": close,
        "v": int(volume),

        # obvously wrong so nobody uses these:
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


def with_high_bias_prescan_strategy(scanner: ScannerFilter):
    """
    Use to map 'h' to 'c' so scanners biased toward highs (e.g. has to be 5% up from previous day close) can cast a wider net during prescanning.
    """

    def _prescanner(tickers: list[Ticker], day: date, candle_getter: CandleGetter, **kwargs) -> list[Ticker]:
        for ticker in tickers:
            ticker['c'] = ticker['h']
        tickers = scanner(tickers, day, candle_getter, **kwargs)
        return tickers

    return _prescanner


def with_shallow_scan_true(f: Callable):
    def _scanner(*args, **kwargs):
        return f(*args, **kwargs, shallow_scan=True)
    return _scanner


def backtest_on_day(day: date, scanner_filter: ScannerFilter, pre_scanner_filter: ScannerFilter,
                    end_time=time(16, 0), start_invoking_time=time(9, 30)
                    ) -> Iterable[HistoricalChronicleEntry]:
    tickers = get_all_tickers_on_day(day, skip_cache=False)

    # Pre-scan pass on daily candles to slim down the number of candidates
    # (assume that prescanner will mutate tickers, so we need to copy)
    mangled_tickers = deepcopy(tickers)
    mangled_tickers = pre_scanner_filter(
        mangled_tickers, day, lambda _1, _2, _3, _4: [])

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
        daily_candles = [build_daily_candle_from_1m_candles(t['T'],
                                                            symbol_to_current_candles[t['T']]) for t in tickers if symbol_to_current_candles[t['T']]]
        daily_candles = [d for d in daily_candles if d]

        # filter candidates, record results
        if current_time.time() >= start_invoking_time:
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
    # TODO: use argparse
    scanner = "meemaw"

    scanner_filter = get_scanner_filter(scanner)

    # TODO: define pre_scanner in each scanner module, don't use these assumptions here for all
    pre_scanner_filter = with_shallow_scan_true(
        with_high_bias_prescan_strategy(scanner_filter))

    # TODO: adjust other scanners to follow the format needed for the above functions
    leadup_period = get_leadup_period(scanner)

    # TODO: pathing
    output_path = "/tmp/meemaw.jsonl"
    try:
        os.remove(output_path)
    except:
        pass

    start, end = get_cache_prepared_date_range_with_leadup_days(leadup_period)

    logging.info(f"start: {start}")
    logging.info(f"end: {end}")
    logging.info(
        f"estimated trading days: {len(list(generate_trading_days(start, end)))}")

    for day in generate_trading_days(start, end):
        candidates = backtest_on_day(
            day, scanner_filter, pre_scanner_filter=pre_scanner_filter)
        jsonl_dump.append_jsonl(output_path, cast(Iterable[dict], candidates))
