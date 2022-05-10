from collections import Counter
import datetime
import os
import typing
from itertools import chain
from src.data.finnhub.finnhub import get_1m_candles
from src.data.polygon.get_option_candles import get_option_candles
from src.data.polygon.option_chain import extract_contract_specifier_from_polygon_option_ticker
from src.data.types.candles import CandleIntraday
from src.outputs.jsonl_dump import append_jsonl

from src.reporting.trades import Trade, build_trade_object, read_trades

# TODO: add new bracket types
# - trailing stop-loss
# - leading take-profit (I made this up)
# - narrowing brackets?


class Bracket(typing.TypedDict):
    # TODO: non-percentage limits
    take_profit_percentage: float
    stop_loss_percentage: float
    # TODO: remove daytrade assumption (time, not datetime) without removing datetime.time support (ease)
    until: datetime.time


def backtest_brackets(input_candles: list[CandleIntraday], input_brackets: list[Bracket], base_price: float) -> typing.Tuple[typing.Optional[float], CandleIntraday, Bracket]:
    """
    Returns sell_price, candle sold on, and bracket during which close occurred
    If no sale occurred, returns None, last candle in brackets, and last bracket in candles

    Caller must handle:
    - timeframing/timeboxing (only pass candles in desired time frame)
    - position entry (pass base_price for calculating percentage limits)
    - timebox exit (if stops/limits not hit and run out of brackets/candles)
    """
    candles = chain(input_candles)
    brackets = chain(input_brackets)

    candle = next(candles)
    bracket = next(brackets)

    try:
        while True:  # will escape because of `next` calls throwing StopIteration
            if candle["datetime"].time() >= bracket["until"]:
                bracket = next(brackets)

            # TODO: non-percentage limits
            take_profit = (1 + bracket["take_profit_percentage"]) * base_price
            stop_loss = (1 - bracket["stop_loss_percentage"]) * base_price

            is_stop_loss = candle["low"] < stop_loss
            is_take_profit = candle["high"] > take_profit

            # TODO: order of conditions as a parameter (so short/put positions can be handled by caller)
            if is_stop_loss:
                return stop_loss, candle, bracket
            if is_take_profit:
                return take_profit, candle, bracket

            candle = next(candles)
    except StopIteration:
        pass

    return None, candle, bracket


def get_option_candles_involved_in_trade(trade: Trade):
    start, end = trade['opened_at'], trade['closed_at']
    # candles = get_1m_candles(trade["symbol"], start.date(), end.date())
    spec = extract_contract_specifier_from_polygon_option_ticker(
        trade["symbol"])
    candles = get_option_candles(spec, '1', start.date(), end.date())
    if not candles:
        raise Exception("No candles found for {}".format(trade["symbol"]))

    return extract_candles_in_range(candles, start, end)


def get_candles_involved_in_trade(trade: Trade):
    start, end = trade['opened_at'], trade['closed_at']
    candles = get_1m_candles(trade["symbol"], start.date(), end.date())
    if not candles:
        raise Exception("No candles found for {}".format(trade["symbol"]))

    return extract_candles_in_range(candles, start, end)


def extract_candles_in_range(candles: list[CandleIntraday], start: datetime.datetime, end: datetime.datetime):
    entry_candle = next(c for c in reversed(
        candles) if c['datetime'] <= start)
    exit_candle = next(c for c in candles if c['datetime'] >= end)
    holding_candles = [
        c for c in candles if c['datetime'] >= entry_candle['datetime'] and c['datetime'] <= exit_candle['datetime']]
    return holding_candles


def get_bracketed_trade(trade: Trade, brackets: list[Bracket]) -> Trade:
    candles = get_option_candles_involved_in_trade(trade)
    new_brackets: list[Bracket] = [{
        "take_profit_percentage": bracket["take_profit_percentage"],
        "stop_loss_percentage": bracket['stop_loss_percentage'],
        "until": trade['closed_at'].time(),  # NOTE: assumes daytrade
    } for bracket in brackets]
    sell_price, last_candle, _last_bracket = backtest_brackets(
        candles, new_brackets, trade['bought_price'])

    if not sell_price:
        sell_price = trade['sold_price']

    closed_at = last_candle['datetime']

    bracketed_trade: Trade = build_trade_object(
        trade['symbol'],
        trade['opened_at'],
        closed_at,
        trade['quantity'],
        trade['bought_price'],
        sell_price
    )
    return bracketed_trade


def main():
    from src.outputs import pathing

    input_path = pathing.get_paths()['data']["dir"] + '/options_trades.jsonl'
    output_path = pathing.get_paths(
    )['data']["dir"] + '/bracketed_trades.jsonl'
    try:
        os.remove(output_path)
    except FileNotFoundError:
        pass

    brackets: list[Bracket] = [{
        "take_profit_percentage": 0.1,
        "stop_loss_percentage": 0.1,
        "until": datetime.time(15, 59),
    }]

    trades = list(read_trades(input_path))
    print(
        f"Base stats: {Counter(trade['is_win'] for trade in trades)} {sum(t['profit_loss'] for t in trades)}")
    bracketed_trades = [get_bracketed_trade(t, brackets) for t in trades]
    print(Counter(t['is_win'] for t in bracketed_trades),
          sum(t['profit_loss'] for t in bracketed_trades))
    append_jsonl(output_path, [typing.cast(dict, t) for t in bracketed_trades])
