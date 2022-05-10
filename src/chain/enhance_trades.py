
import os
import typing

from src.chain.gramma import simulate_trade_in_options
from src.data.polygon.option_chain import format_contract_specifier_to_polygon_option_ticker
from src.reporting.trades import Trade, read_trades
from src.outputs import jsonl_dump


def translate_trades_to_options(trades: typing.Iterator[Trade]) -> typing.Iterator[Trade]:
    for trade in trades:
        simulation_result = simulate_trade_in_options(
            trade['symbol'], trade['opened_at'], trade['closed_at'], trade['quantity'] > 0)
        if not simulation_result:
            continue

        # TODO: sizing?
        quantity = 1
        bought_cost = quantity*simulation_result['open']
        sold_cost = quantity*simulation_result['close']
        options_trade: Trade = {
            "symbol": format_contract_specifier_to_polygon_option_ticker(simulation_result['contract']['spec']),
            "opened_at": trade["opened_at"],
            "closed_at": trade["closed_at"],
            "quantity": quantity,

            "bought_price": round(simulation_result['open'], 4),
            "sold_price": round(simulation_result['close'], 4),

            "bought_cost": round(bought_cost, 4),
            "sold_cost": round(sold_cost, 4),

            "price_difference": round(simulation_result['close'] - simulation_result['open'], 4),
            "profit_loss": round(sold_cost - bought_cost, 4),
            "roi": round((sold_cost - bought_cost) / bought_cost, 4),
            "is_win": sold_cost > bought_cost,
        }
        yield options_trade


def main():
    from src.outputs import pathing
    # TODO: make this a command line argument
    input_path = pathing.get_paths()['data']["dir"] + '/trades.jsonl'
    output_path = pathing.get_paths()['data']["dir"] + '/options_trades.jsonl'
    try:
        os.remove(output_path)
    except FileNotFoundError:
        pass

    trades = read_trades(input_path)
    for trade in translate_trades_to_options(trades):
        print(trade['closed_at'])
        jsonl_dump.append_jsonl(output_path, [typing.cast(dict, trade)])
