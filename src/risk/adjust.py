import copy

from src.risk import simulate_account
from src import trading_day


def main():
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument("result_name", type=str)

    args = parser.parse_args()

    from src.results import read_results

    orders = list(read_results.get_orders(args.result_name))

    portfolio_percentage = 0.062

    # large so percentage choppiness/error are smaller
    initial_account_value = 1_000_000_000

    initial_account = simulate_account.SettlingAccountState(
        initial_account_value, simulate_account.IdealAccountState(initial_account_value, simulate_account.build_td_simulation(), {}), [])
    account = copy.deepcopy(initial_account)
    for order in orders:
        # TODO: evaluate at proper time of day, not close (then update portfolio_value_estimator_version)
        # portfolio_value = simulate_account.estimate_account_value(
        #     account.ideal_account_state, order.datetime.date())
        portfolio_value = account.get_cash() + account.get_settling_cash_amount()
        cash_to_use = portfolio_percentage * portfolio_value
        # TODO: do I have purchasing power to do this? Add limiter

        adjusted_order = copy.deepcopy(order)
        adjusted_order.add_intention_field(
            "adjusted.original_quantity", order.quantity)
        adjusted_order.add_intention_field(
            "adjusted.portfolio_value", portfolio_value)
        adjusted_order.add_intention_field(
            "adjusted.portfolio_value_estimator_version", "v3")
        adjusted_order.add_intention_field(
            "adjusted.portfolio_percentage", portfolio_percentage)

        if adjusted_order.is_buy():
            adjusted_order.quantity = cash_to_use // order.quantity
        elif adjusted_order.is_sell():
            # NOTE: assumes all sells are 100% liquidations... awkward
            adjusted_order.quantity = -account.get_positions()[
                adjusted_order.symbol]

        changes = simulate_account.apply_order_to_settling_account(
            account, adjusted_order)
        account = changes[-1][1]

        print(account.get_positions(), account.get_cash())
