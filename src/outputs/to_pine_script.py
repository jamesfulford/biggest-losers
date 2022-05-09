from src.reporting.trades import Order, SimpleTrade, get_virtual_orders_of_simple_trade, read_trades
import datetime
import typing


def serialize_order_to_pine_script(order: Order) -> str:
    s = ""
    s += f"array.push(trade_times, {int(order['datetime'].timestamp())}000)\n"
    s += f"array.push(trade_is_long, {'true' if order['is_long'] else 'false'})\n"
    is_add = order['quantity'] > 0 if order['is_long'] else order['quantity'] < 0
    s += f"array.push(trade_is_add, {'true' if is_add else 'false'})\n"
    return s


def build_script(orders: typing.Iterable[Order]) -> str:
    script = f"""
// This source code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// © jamesfulford
//@version=5
indicator("Backtest Trades", overlay=true)

int[] trade_times = array.new_int(0)
bool[] trade_is_long = array.new_bool(0)
bool[] trade_is_add = array.new_bool(0)
    """

    for order in orders:
        script += serialize_order_to_pine_script(order) + '\n'

    script += """
i = array.indexof(trade_times, time)
x = i != -1
is_long = if x
    array.get(trade_is_long, i)
is_add = if x
    array.get(trade_is_add, i)
plotshape(x and is_long and is_add, style=shape.labeldown, color=color.green, text="L", textcolor=color.black)
plotshape(x and is_long and not is_add, style=shape.labeldown, color=color.red, text="L", textcolor=color.black)
plotshape(x and not is_long and is_add, style=shape.labeldown, color=color.green, text="S", textcolor=color.black)
plotshape(x and not is_long and not is_add, style=shape.labeldown, color=color.red, text="S", textcolor=color.black)
    """
    return script


def main():
    # TODO: read orders, not trades
    input_path = "/Users/jamesfulford/Downloads/trades.jsonl"

    orders = []
    for trade in read_trades(input_path):
        orders.extend(get_virtual_orders_of_simple_trade(
            typing.cast(SimpleTrade, trade)))

    print(build_script(orders))
