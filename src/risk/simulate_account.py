import datetime
import itertools
import logging
import typing
from src import trading_day, types


class SimulationParameters(typing.TypedDict):
    commission_per_order: float
    commission_per_share: float
    commission_per_contract: float


def build_td_simulation() -> SimulationParameters:
    return {
        'commission_per_order': 0,
        'commission_per_share': 0,
        'commission_per_contract': 0.0075 * 100,
    }


def simulate_account(orders: typing.Iterator[types.FilledOrder], initial_cash: float, parameters: SimulationParameters) -> typing.Iterator[typing.Tuple[types.FilledOrder, float]]:
    commission_per_order = parameters['commission_per_order']
    commission_per_share = parameters['commission_per_share']
    commission_per_contract = parameters['commission_per_contract']

    cash = initial_cash  # settled cash that can be used for purchasing

    for order in orders:
        value = order.get_position_difference()
        size = abs(order.quantity)

        diff = value - (commission_per_contract if order.is_option()
                        else commission_per_share) * size - commission_per_order
        cash += diff

        yield (order, cash)


def find_perfect_initial_balance(orders: typing.Iterator[types.FilledOrder], simulation_parameters: SimulationParameters) -> float:
    # negative lowest low point -> just enough initial balance to never go below 0
    return -min(simulate_account(orders, 0, simulation_parameters), key=lambda t: t[1])[1]


def find_min_balance_needed_for_purchasing_power(orders: typing.Iterator[types.FilledOrder], simulation_parameters: SimulationParameters) -> float:
    return -min(yield_running_purchasing_power_with_settling(orders, simulation_parameters), key=lambda e: e[1])[1]


def yield_running_purchasing_power_with_settling(orders: typing.Iterator[types.FilledOrder], simulation_parameters: SimulationParameters) -> typing.Iterator[typing.Tuple[datetime.datetime, float]]:
    previous_cash = 0
    # when demand for cash (buying), cash goes down
    # when supply of cash (selling), cash goes up after settling period
    purchasing_power = 0
    # (day when cash becomes available, cash that will become available)
    settling_purgatory = []
    for order, cash in simulate_account(orders, 0, simulation_parameters):

        # At start of day (assumed 9:30), increase purchasing power from pending cash settling
        if any(e[0] <= order.datetime.date() for e in settling_purgatory):
            for settlement_date, settlement_usage in settling_purgatory:
                if settlement_date <= order.datetime.date():
                    purchasing_power += settlement_usage
            settling_purgatory = [(settlement_date, settlement_usage) for settlement_date,
                                  settlement_usage in settling_purgatory if settlement_date > order.datetime.date()]
            yield typing.cast(datetime.datetime, trading_day.get_market_open_on_day(order.datetime.date())), purchasing_power

        cash_diff = previous_cash - cash
        previous_cash = cash

        if cash_diff > 0:
            purchasing_power -= cash_diff
            yield order.datetime, purchasing_power
        else:
            # money is flowing in, schedule the cash to settle in the future
            # Options actually settle in 1 day: https://td.intelliresponse.com/tddirectinvesting/public/index.jsp?interfaceID=19&sessionId=921723fb-d96f-11ec-b911-43daeb48e13c&id=7551&requestType=&source=9&question=settled+
            # TODO: `1 or 2` better configuration needed(?)
            settlement_release_day = trading_day.n_trading_days_ahead(
                order.datetime.date(), 1 if order.is_option() else 2)
            settling_purgatory_entry = (settlement_release_day, abs(cash_diff))
            settling_purgatory.append(settling_purgatory_entry)

    prev_day = min(settling_purgatory, key=lambda t: t[0])[
        0] if settling_purgatory else None
    if not prev_day:
        return

    for settlement_date, settlement_usage in sorted(settling_purgatory):
        if settlement_date > prev_day:
            yield typing.cast(datetime.datetime, trading_day.get_market_open_on_day(prev_day)), purchasing_power
            prev_day = settlement_date
        purchasing_power += settlement_usage

    yield typing.cast(datetime.datetime, trading_day.get_market_open_on_day(prev_day)), purchasing_power


def simulate_final_profit_loss(orders: typing.Iterator[types.FilledOrder], simulation_parameters: SimulationParameters):
    last_cash = 0
    for _order, cash in simulate_account(orders, 0, simulation_parameters):
        last_cash = cash
    return last_cash


def yield_last_by_date(tuples: typing.Iterator[typing.Tuple[datetime.datetime, float]]) -> typing.Iterator[typing.Tuple[datetime.date, float]]:
    prev_dt, prev_value = next(tuples, (None, 0))
    if not prev_dt:
        return
    prev_day = prev_dt.date()

    for day, value in itertools.chain([(prev_dt, prev_value)], tuples):
        if day.date() != prev_day:
            yield prev_day, prev_value
        prev_day = day.date()
        prev_value = value
    yield prev_day, prev_value


def main():
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument("result_name", type=str)

    args = parser.parse_args()

    from src.results import read_results

    orders = list(read_results.get_orders(args.result_name))

    simulation_parameters = build_td_simulation()

    perfect_initial_balance = find_perfect_initial_balance(
        iter(orders), simulation_parameters)
    cash_initial_balance = find_min_balance_needed_for_purchasing_power(
        iter(orders), simulation_parameters)

    pnl = simulate_final_profit_loss(iter(orders), simulation_parameters)

    print(
        f"Perfect initial balance: {perfect_initial_balance:>8.2f} \tfinal balance: {(perfect_initial_balance + pnl):>8.2f} \tROI: {pnl / perfect_initial_balance:>8.2%}")
    print(
        f"Cash initial balance   : {cash_initial_balance:>8.2f} \tfinal balance: {(cash_initial_balance + pnl):>8.2f} \tROI: {pnl / cash_initial_balance:>8.2%}")

    # print()
    # print("  Time           Purchasing power in cash account by end of day")
    # for dt, purchasing_power in yield_last_by_date(yield_running_purchasing_power_with_settling(iter(orders), simulation_parameters)):
    #     print(
    #         f"  {dt} {cash_initial_balance+purchasing_power:>12.2f}")
    # print()
