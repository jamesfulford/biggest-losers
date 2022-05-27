import collections
import datetime
import itertools
from src.results import read_results, from_backtest, metadata


def get_first_n_trades_of_each_symbol(trades_feed, n: int):
    first_trade = next(trades_feed)
    current_day = first_trade.get_start().date()

    counts = {}
    for trade in itertools.chain([first_trade], trades_feed):
        if trade.get_start().date() != current_day:
            counts = {}
            current_day = trade.get_start().date()

        symbol = trade.get_symbol()
        counts[symbol] = counts.get(symbol, 0) + 1
        if counts[symbol] > n:
            print('\tskipping', current_day, symbol)
            continue

        yield trade


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("source_results_name", type=str)
    parser.add_argument("dest_results_name", type=str)
    parser.add_argument("--max-n-trades", type=int, default=1)
    args = parser.parse_args()
    source_results_name = args.source_results_name
    dest_results_name = args.dest_results_name
    max_n_trades = args.max_n_trades

    trades_feed = iter(read_results.get_trades(source_results_name))
    # NOTE: this is for day-trading specifically

    new_orders = []
    for trade in get_first_n_trades_of_each_symbol(
            trades_feed, max_n_trades):
        print(trade.get_start().date(), trade.get_symbol())
        new_orders.extend(trade.orders)

    from_backtest.write_results(dest_results_name, new_orders, metadata.Metadata(
        commit_id='', last_updated=datetime.datetime.now()))
