import itertools
import logging
import typing
from src import types


class SimulationParameters(typing.TypedDict):
    commission_per_order: float
    commission_per_share: float
    price_slippage: float


def build_perfect_simulation():
    return {
        'commission_per_order': 0,
        'commission_per_share': 0,
        'price_slippage': 0
    }


def build_td_options_simulation(typical_spread: float = 0.05):
    return {
        'commission_per_order': 0,
        # 0.75c per share per option contract per order. (buy+sell 1 contract of 100 -> $1.3)
        'commission_per_share': 0.0075,
        # assumes mark is usually halfway between bid and ask
        'price_slippage': typical_spread * .5
    }


def build_commission_free_stock_simulation(typical_spread: float = 0.05):
    return {
        'commission_per_order': 0,
        'commission_per_share': 0,
        # assumes mark is usually halfway between bid and ask
        'price_slippage': typical_spread * .5
    }


def simulate_account(trades: typing.Iterator[types.Trade], initial_cash: float, parameters: SimulationParameters) -> typing.Iterator[typing.Tuple[types.Trade, float, float]]:
    commission_per_order = parameters['commission_per_order']
    commission_per_share = parameters['commission_per_share']
    price_slippage = parameters['price_slippage']

    cash = initial_cash
    for trade in trades:
        value_spent = (trade.get_average_entry_price() +
                       price_slippage) * trade.get_quantity()

        cash -= value_spent
        cash -= commission_per_order
        cash -= commission_per_share * trade.get_quantity()

        low_point = cash

        value_extracted = (trade.get_average_exit_price() -
                           price_slippage) * trade.get_quantity()

        cash += value_extracted
        cash -= commission_per_order

        yield (trade, low_point, cash)


def find_perfect_initial_balance(trades, simulation_parameters: SimulationParameters) -> float:
    # negative lowest low point -> just enough initial balance to never go below 0
    return -min(simulate_account(trades, 0, simulation_parameters), key=lambda t: t[1])[1]


def yield_usages(trades: typing.Iterator[types.Trade], simulation_parameters: SimulationParameters) -> typing.Iterator[typing.Tuple[types.Trade, float]]:
    """Includes commissions and simulated slippage"""
    previous_cash = 0
    for trade, low_point, cash in simulate_account(trades, 0, simulation_parameters):
        yield (trade, previous_cash - low_point)
        previous_cash = cash


def find_max_usage(trades: typing.Iterator[types.Trade], simulation_parameters: SimulationParameters) -> float:
    return max(yield_usages(trades, simulation_parameters), key=lambda t: t[1])[1]


def yield_daily_usages(trades: typing.Iterator[types.Trade], simulation_parameters: SimulationParameters) -> typing.Iterator[typing.Tuple[types.Trade, float]]:
    first_trade = next(trades)
    current_date = first_trade.get_end().date()
    current_usage = 0
    for trade, usage in yield_usages(itertools.chain([first_trade], trades), simulation_parameters):
        if trade.get_end().date() != current_date:
            current_date = trade.get_end().date()
            yield (trade, current_usage)
            current_usage = 0
        current_usage += usage


def pairwise(l: list, n=2):
    i = 0
    while True:
        slic = l[i:i+n]
        if len(slic) != n:
            break
        yield slic
        i += 1


def find_max_rolling_daily_usage(trades: typing.Iterator[types.Trade], window_size: int, simulation_parameters: SimulationParameters) -> float:
    tuple_pairs = pairwise(
        [daily_usage for daily_usage in yield_daily_usages(trades, simulation_parameters)], window_size)
    highest_usage_pair = max(
        tuple_pairs, key=lambda tp_pair: sum(tp[1] for tp in tp_pair))
    return sum(tp[1] for tp in highest_usage_pair)


def find_perfect_initial_balance_for_cash_account(trades, simulation_parameters: SimulationParameters):
    # settle period is 2 days
    return find_max_rolling_daily_usage(trades, 2, simulation_parameters)


def find_perfect_initial_balance_for_margin_account(trades, simulation_parameters: SimulationParameters):
    return find_max_rolling_daily_usage(trades, 1, simulation_parameters)


def simulate_final_profit_loss(trades, simulation_parameters: SimulationParameters):
    last_cash = 0
    for trade, low_point, cash in simulate_account(trades, 0, simulation_parameters):
        last_cash = cash
    return last_cash


def main():
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument("result_name", type=str)
    parser.add_argument("parameter_set", type=str,
                        help="commission_free_stock, ")

    args = parser.parse_args()

    from src.results import read_results

    trades = list(read_results.get_trades(args.result_name))

    simulation_parameters = build_perfect_simulation()
    if args.parameter_set.startswith('td_options'):
        # like "td_options[0.05]"
        typical_spread = args.parameter_set.split('[')[1].split(']')[0]
        typical_spread = float(typical_spread)
        logging.info(
            f"Using TD Options simulation parameters with typical spread of {typical_spread}")
        simulation_parameters = build_td_options_simulation(typical_spread)
    if args.parameter_set.startswith('commission_free_stock'):
        typical_spread = args.parameter_set.split('[')[1].split(']')[0]
        typical_spread = float(typical_spread)
        logging.info(
            f"Using commission free stock simulation parameters with typical spread of {typical_spread}")
        simulation_parameters = build_commission_free_stock_simulation(
            typical_spread)
    else:
        logging.warning(
            f"Using perfect simulation parameters, results are optimistic")

    margin_initial_balance = find_perfect_initial_balance_for_margin_account(
        iter(trades), simulation_parameters)
    cash_initial_balance = find_perfect_initial_balance_for_cash_account(
        iter(trades), simulation_parameters)
    perfect_initial_balance = find_perfect_initial_balance(
        iter(trades), simulation_parameters)

    pnl = simulate_final_profit_loss(iter(trades), simulation_parameters)

    print(
        f"Perfect initial balance: {perfect_initial_balance:>8.2f} \tfinal balance: {(perfect_initial_balance + pnl):>8.2f} \tROI: {pnl / perfect_initial_balance:>8.2%}")
    # Options actually settle in 1 day: https://td.intelliresponse.com/tddirectinvesting/public/index.jsp?interfaceID=19&sessionId=921723fb-d96f-11ec-b911-43daeb48e13c&id=7551&requestType=&source=9&question=settled+
    print(
        f"Margin initial balance : {margin_initial_balance:>8.2f} \tfinal balance: {(margin_initial_balance + pnl):>8.2f} \tROI: {pnl / margin_initial_balance:>8.2%}")
    print(
        f"Cash initial balance   : {cash_initial_balance:>8.2f} \tfinal balance: {(cash_initial_balance + pnl):>8.2f} \tROI: {pnl / cash_initial_balance:>8.2%}")
