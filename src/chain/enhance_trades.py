
import datetime
import os
import typing

from src.chain.gramma import simulate_trade_in_options
from src.data.polygon.option_chain import format_contract_specifier_to_polygon_option_ticker
from src.reporting.trades import Trade, read_trades
from src.outputs import jsonl_dump

from src import types


def translate_trades_to_options_orders(trades: typing.Iterator[types.Trade]) -> typing.Iterator[types.FilledOrder]:
    for trade in trades:
        simulation_result = simulate_trade_in_options(
            trade.get_symbol(), trade.get_start(), trade.get_end(), trade.is_long())
        if not simulation_result:
            continue

        symbol = format_contract_specifier_to_polygon_option_ticker(
            simulation_result['contract']['spec'])

        # TODO: simulate each order instead of just virtual open and close (so we can pass along intentions)
        # TODO: consider sizing based off of cash usage in original trades?
        # for order in trade.orders:
        #     types.FilledOrder(
        #         intention=order.intention,
        #         symbol=symbol,
        #         quantity=order.quantity,
        #         price=
        #     )

        yield types.FilledOrder(
            intention=None,
            symbol=symbol,
            quantity=1,
            price=simulation_result['open'],
            datetime=trade.get_start(),
        )
        yield types.FilledOrder(
            intention=None,
            symbol=symbol,
            quantity=-1,
            price=simulation_result['close'],
            datetime=trade.get_end(),
        )


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("result_name", type=str)
    parser.add_argument("output_result_name", type=str)
    # TODO: select option-picker algorithm
    args = parser.parse_args()

    assert args.result_name != args.output_result_name, "result_name and output_result_name must be different"

    import src.results.read_results as read_results

    trades = read_results.get_trades(args.result_name)

    # TODO: resolve this issue
    # Finnhub does not allow going back too far
    trades = (t for t in trades if t.get_start().date() > datetime.date.today(
    ) - datetime.timedelta(days=364))

    options_orders = translate_trades_to_options_orders(trades)

    from src.results import from_backtest, metadata

    from_backtest.write_results(args.output_result_name, list(
        options_orders), metadata.Metadata(commit_id="", last_updated=datetime.datetime.now()))
