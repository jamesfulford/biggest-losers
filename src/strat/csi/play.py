import datetime
import typing

from src import types
from src.data.polygon import get_candles
from src.data.types.candles import CandleInterday


import numpy as np
from talib.abstract import RSI

ETFS = ['XLE', 'XLU', 'XLV', 'XLF', 'XLB',
        'XLI', 'XLRE', 'XLK', 'XLY', 'XLC', 'XLP']


def yield_csis(candles: list[CandleInterday]) -> typing.Iterable[typing.Tuple[CandleInterday, float]]:
    candles_so_far: list[CandleInterday] = []
    for candle in candles:
        candles_so_far.append(candle)
        try:
            candle_1m = candles_so_far[-1 * 22]
            candle_3m = candles_so_far[-3 * 22]
            candle_6m = candles_so_far[-6 * 22]
        except:
            continue

        pct_1m = (candle['close'] - candle_1m['close']) / \
            candle_1m['close']
        pct_3m = (candle['close'] - candle_3m['close']) / \
            candle_3m['close']
        pct_6m = (candle['close'] - candle_6m['close']) / \
            candle_6m['close']
        csi = (pct_1m + pct_3m + pct_6m) / 3
        yield candle, csi


def rank_symbols_by_csi(candles_by_symbol):
    csis_by_symbol_by_day = {}
    for symbol, candles in candles_by_symbol.items():
        for t, csi in yield_csis(candles):
            day = t['date']
            csis_by_symbol = csis_by_symbol_by_day.get(day, {})
            csis_by_symbol[symbol] = round(100*csi, 1)
            csis_by_symbol_by_day[day] = csis_by_symbol

    for day, csis_by_symbol in sorted(csis_by_symbol_by_day.items()):
        ranked = sorted(csis_by_symbol.items(),
                        key=lambda v: v[1], reverse=True)
        yield day, ranked


def yield_changes_in_sets(day_set_yielder):
    previous_symbols = set()
    for day, current_symbols in day_set_yielder:

        if previous_symbols.symmetric_difference(current_symbols):
            to_sell = previous_symbols.difference(current_symbols)
            to_buy = current_symbols.difference(previous_symbols)
            yield day, to_sell, to_buy

        previous_symbols = current_symbols


def convert_day_set_yielder_to_orders(day_set_yielder, candles_by_symbol):
    state = {}
    for day, removed, added in yield_changes_in_sets(day_set_yielder):
        for symbol in removed:
            # get day after
            candle_to_sell = next(
                filter(lambda c: c['date'] > day, candles_by_symbol[symbol]), None)
            if not candle_to_sell:
                continue
            quantity = -state[symbol]
            del state[symbol]
            order = types.FilledOrder(intention=None, symbol=symbol, quantity=quantity, price=candle_to_sell['open'], datetime=datetime.datetime.combine(
                candle_to_sell['date'], datetime.time(9, 30), tzinfo=get_candles.MARKET_TIMEZONE))
            yield order

        for symbol in added:
            # get day after
            candle_to_sell = next(
                filter(lambda c: c['date'] > day, candles_by_symbol[symbol]), None)
            if not candle_to_sell:
                continue
            quantity = int(10000 / candle_to_sell['open'])
            state[symbol] = quantity
            order = types.FilledOrder(intention=None, symbol=symbol, quantity=quantity, price=candle_to_sell['open'], datetime=datetime.datetime.combine(
                candle_to_sell['date'], datetime.time(9, 30), tzinfo=get_candles.MARKET_TIMEZONE))
            yield order


def main():
    today = datetime.date.today()
    start, end = today.replace(
        year=today.year - 2), today - datetime.timedelta(days=1)

    symbols = ETFS
    candles_by_symbol = {symbol: typing.cast(list[CandleInterday], get_candles.get_candles(
        symbol, 'D', start, end)) for symbol in symbols}

    top_n = int(len(symbols) ** .5)  # pareto principle
    csi_day_set_yielder = list((day, set(
        symbol for symbol, score in rankings[:top_n])) for day, rankings in rank_symbols_by_csi(candles_by_symbol))

    for day, symbol_set in csi_day_set_yielder:
        print(day, symbol_set)

    # Raw
    from src.results import from_backtest, metadata
    from_backtest.write_results('csi', list(convert_day_set_yielder_to_orders(
        csi_day_set_yielder, candles_by_symbol)), metadata.Metadata('', datetime.datetime.now()))

    from_backtest.write_results('csi-with-rsi', sorted(csi_with_rsi_entry(
        candles_by_symbol, csi_day_set_yielder), key=lambda o: o.datetime), metadata.Metadata('', datetime.datetime.now()))


def csi_with_rsi_entry(candles_by_symbol, csi_day_set_yielder):
    for symbol, candles in candles_by_symbol.items():
        candles = candles
        rsi_line = typing.cast(list[float], RSI({
            "open": np.array(list(map(lambda c: float(c["open"]), candles))),
            "high": np.array(list(map(lambda c: float(c["high"]), candles))),
            "low": np.array(list(map(lambda c: float(c["low"]), candles))),
            "close": np.array(list(map(lambda c: float(c["close"]), candles))),
            "volume": np.array(list(map(lambda c: float(c["volume"]), candles))),
        }, timeperiod=5).tolist())

        previous_set, current_set = set(), set()
        previous_rsi, current_rsi = None, None

        is_entered = False
        quantity_holding = 0
        # reversing to avoid writing code to align the generators (csi skips first 6 months of candles because of how its defined)
        for candle, rsi, (day, symbol_set) in reversed(list(zip(reversed(candles), reversed(rsi_line), reversed(csi_day_set_yielder)))):
            assert candle['date'] == day, 'streams are unaligned, revisit code'
            previous_set, current_set = current_set, symbol_set
            previous_rsi, current_rsi = current_rsi, rsi

            if is_entered:
                # exit criteria
                if rsi > 80:
                    # if rsi > 80 or symbol not in symbol_set:
                    candle_to_sell = next(
                        filter(lambda c: c['date'] > day, candles_by_symbol[symbol]), None)
                    if not candle_to_sell:
                        continue
                    price = candle_to_sell['open']
                    date = candle_to_sell['date']
                    quantity = -quantity_holding
                    order = types.FilledOrder(intention=None, symbol=symbol, quantity=quantity, price=price, datetime=datetime.datetime.combine(
                        date, datetime.time(9, 30), tzinfo=get_candles.MARKET_TIMEZONE))
                    yield order

                    is_entered = False
                    quantity_holding = 0
                continue

            # must show on scanner
            if symbol not in symbol_set:
                continue

            # entry criteria
            # if symbol not in previous_set:
            # if rsi < 30:
            if rsi > 40 and (previous_rsi and previous_rsi < 40):
                # process entry
                # print(symbol, day, previous_set, symbol_set)
                candle_to_sell = next(
                    filter(lambda c: c['date'] > day, candles_by_symbol[symbol]), None)
                if not candle_to_sell:
                    continue
                price = candle_to_sell['open']
                date = candle_to_sell['date']
                quantity = int(10000 / candle['close'])
                order = types.FilledOrder(intention=None, symbol=symbol, quantity=quantity, price=price, datetime=datetime.datetime.combine(
                    date, datetime.time(9, 30), tzinfo=get_candles.MARKET_TIMEZONE))
                yield order

                quantity_holding = quantity
                is_entered = True

        if is_entered:
            candle_to_sell = candles_by_symbol[symbol][-1]
            # estimate remaining value
            price = candle_to_sell['close']
            quantity = -quantity_holding
            date = candle_to_sell['date']
            quantity = -quantity_holding
            order = types.FilledOrder(intention=None, symbol=symbol, quantity=quantity, price=price, datetime=datetime.datetime.combine(
                date, datetime.time(16, 0), tzinfo=get_candles.MARKET_TIMEZONE))
            yield order
