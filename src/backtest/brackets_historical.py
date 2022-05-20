from collections import Counter
import datetime
import typing
from itertools import chain
from src.data.finnhub.finnhub import get_1m_candles
from src.data.polygon.get_option_candles import get_option_candles
from src.data.polygon.option_chain import extract_contract_specifier_from_polygon_option_ticker
from src.data.types.candles import CandleIntraday

from src import types

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


def get_option_candles_involved_in_trade(trade: types.Trade):
    start, end = trade.get_start(), trade.get_end()
    # candles = get_1m_candles(trade["symbol"], start.date(), end.date())
    spec = extract_contract_specifier_from_polygon_option_ticker(
        trade.get_symbol())
    candles = get_option_candles(spec, '1', start.date(), end.date())
    if not candles:
        raise Exception("No candles found for {}".format(trade.get_symbol()))

    return extract_candles_in_range(candles, start, end)


def get_candles_involved_in_trade(trade: types.Trade):
    start, end = trade.get_start(), trade.get_end()
    candles = get_1m_candles(trade.get_symbol(), start.date(), end.date())
    if not candles:
        raise Exception("No candles found for {}".format(trade.get_symbol()))

    return extract_candles_in_range(candles, start, end)


def extract_candles_in_range(candles: list[CandleIntraday], start: datetime.datetime, end: datetime.datetime):
    entry_candle = next(c for c in reversed(
        candles) if c['datetime'] <= start)
    exit_candle = next(c for c in candles if c['datetime'] >= end)
    holding_candles = [
        c for c in candles if c['datetime'] >= entry_candle['datetime'] and c['datetime'] <= exit_candle['datetime']]
    return holding_candles


def get_bracketed_virtual_trade(trade: types.Trade, brackets: list[Bracket]) -> types.Trade:
    candles = get_option_candles_involved_in_trade(trade)
    new_brackets: list[Bracket] = [{
        "take_profit_percentage": bracket["take_profit_percentage"],
        "stop_loss_percentage": bracket['stop_loss_percentage'],
        "until": trade.get_end().time(),  # NOTE: assumes daytrade
    } for bracket in brackets]
    sell_price, last_candle, _last_bracket = backtest_brackets(
        candles, new_brackets, trade.get_average_entry_price())

    if not sell_price:
        sell_price = trade.get_average_exit_price()

    closed_at = last_candle['datetime']

    # TODO: how to not do virtual orders with brackets?
    original_entry_virtual_order, _original_exit_virtual_order = trade.get_virtual_orders()

    return types.Trade(orders=[
        original_entry_virtual_order,
        types.FilledOrder(
            intention=None,
            symbol=trade.get_symbol(),
            price=sell_price,
            quantity=-trade.get_quantity(),
            datetime=closed_at,
        )])


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("result_name", type=str)
    parser.add_argument("output_result_name", type=str)
    parser.add_argument("--brackets", type=str, default="20,20")
    # TODO: select option-picker algorithm
    args = parser.parse_args()

    assert args.result_name != args.output_result_name, "result_name and output_result_name must be different"

    stop_loss, take_profit = [float(x) / 100 for x in args.brackets.split(",")]
    brackets: list[Bracket] = [{
        "take_profit_percentage": take_profit,
        "stop_loss_percentage": stop_loss,
        "until": datetime.time(15, 59),
    }]

    import src.results.read_results as read_results

    trades = read_results.get_trades(args.result_name)

    # TODO: resolve this issue
    # Finnhub does not allow going back too far
    trades = [t for t in trades if t.get_start().date() > datetime.date.today(
    ) - datetime.timedelta(days=364)]

    print(f"Base stats:")
    print(f"  win/loss: {Counter(trade.is_win() for trade in trades)}")
    print(f"  profit:   {sum(t.get_profit_loss() for t in trades):.2f}")

    brack_trades = [get_bracketed_virtual_trade(
        trade, brackets) for trade in trades]

    print(f"New stats:")
    print(f"  win/loss: {Counter(trade.is_win() for trade in brack_trades)}")
    print(f"  profit:   {sum(t.get_profit_loss() for t in brack_trades):.2f}")

    bracketed_orders = []
    for bracketed_trade in brack_trades:
        bracketed_orders.extend(bracketed_trade.orders)

    from src.results import from_backtest, metadata

    from_backtest.write_results(args.output_result_name, bracketed_orders, metadata.Metadata(
        commit_id="", last_updated=datetime.datetime.now()))
