from src.outputs import pathing
from src.reporting.trades import Order, SimpleTrade, get_virtual_orders_of_simple_trade, read_trades
import typing
import src.types as types


def serialize_order_to_pine_script(order: types.FilledOrder) -> str:
    s = ""
    s += f"array.push(trade_times, {int(order.datetime.timestamp())}000)\n"
    s += f"array.push(trade_is_add, {'true' if order.is_buy() else 'false'})\n"
    return s


def build_script(orders: typing.Iterable[types.FilledOrder]) -> str:
    script = f"""
// This source code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// © jamesfulford
//@version=5
indicator("Backtest Trades", overlay=true)

int[] trade_times = array.new_int(0)
bool[] trade_is_add = array.new_bool(0)
    """
    script += "\n"

    for order in orders:
        script += serialize_order_to_pine_script(order) + '\n'

    script += """
i = array.indexof(trade_times, time)
x = i != -1
is_long = if x
    array.get(trade_is_long, i)
is_add = if x
    array.get(trade_is_add, i)
plotshape(x and is_add, style=shape.labeldown, color=color.green, text="+", textcolor=color.black)
plotshape(x and not is_add, style=shape.labeldown, color=color.red, text="-", textcolor=color.black)
    """
    return script


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("result_name", type=str)
    args = parser.parse_args()

    import src.results.read_results as read_results

    orders = read_results.get_orders(args.result_name)

    print(build_script(orders))
