from pprint import pprint
import copy

import datetime
import itertools
import logging
import typing

import pandas as pd
import quantstats

from src import trading_day, types
from src.data.polygon import get_candles

#
# Parameters to control ideal simulation (no settlement)
#


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


#
# Naive theoretical account (with commissions, but no settling)
#
class IdealAccountState:
    def __init__(self, initial_balance: float, simulation_parameters: SimulationParameters, positions: typing.Optional[dict[str, float]]):
        self.cash = initial_balance
        self.simulation_parameters = simulation_parameters
        self.positions = positions if positions else {}

    @staticmethod
    def empty(parameters: SimulationParameters):
        return IdealAccountState(0, parameters, {})


def apply_order_to_account_state(state: IdealAccountState, order: types.FilledOrder) -> IdealAccountState:
    # update positions
    current_qty = state.positions.get(order.symbol, 0)
    new_qty = current_qty + order.quantity

    new_positions = copy.copy(state.positions)
    new_positions[order.symbol] = new_qty
    if new_positions[order.symbol] == 0:
        del new_positions[order.symbol]

    # update cash
    size = abs(order.quantity)
    diff = order.get_position_difference() - (state.simulation_parameters['commission_per_contract'] if order.is_option()
                                              else state.simulation_parameters['commission_per_share']) * size - state.simulation_parameters['commission_per_order']
    new_balance = round(state.cash + diff, 6)

    return IdealAccountState(new_balance, state.simulation_parameters, new_positions)


#
# Account with settling (wraps IdealAccountState)
#
class SettlingAccountState:
    def __init__(self, purchasing_power: float, ideal_account_state: IdealAccountState, settling_purgatory: list[typing.Tuple[datetime.datetime, float]]):
        self.ideal_account_state = ideal_account_state
        self.settling_purgatory = settling_purgatory
        self.purchasing_power = purchasing_power

    def get_settling_cash_amount(self) -> float:
        return sum(usage for _, usage in self.settling_purgatory)

    def get_settling_purgatory(self) -> list[typing.Tuple[datetime.datetime, float]]:
        """
        (date where emerges from settlement, amount that will be added to purchasing power)
        """
        return self.settling_purgatory

    def get_cash(self) -> float:
        return self.ideal_account_state.cash

    def get_purchasing_power(self) -> float:
        return self.purchasing_power

    def get_positions(self) -> dict[str, float]:
        return self.ideal_account_state.positions


def apply_order_to_settling_account(settling_account_state: SettlingAccountState, order: types.FilledOrder) -> list[typing.Tuple[datetime.datetime, SettlingAccountState]]:
    # At start of day (assumed 9:30), increase purchasing power from pending cash settling
    new_purchasing_power = settling_account_state.purchasing_power
    new_settling_purgatory = copy.deepcopy(
        settling_account_state.settling_purgatory)
    new_settling_account_state = copy.deepcopy(settling_account_state)

    changes: list[typing.Tuple[datetime.datetime,
                               SettlingAccountState]] = []

    # process settling purgatory before processing order
    for settlement_datetime, settlement_usage in filter(lambda t: t[0] <= order.datetime, settling_account_state.settling_purgatory):
        new_purchasing_power += settlement_usage
        new_settling_purgatory = [(settlement_datetime, settlement_usage) for settlement_datetime,
                                  settlement_usage in new_settling_purgatory if settlement_datetime > order.datetime]
        new_settling_account_state = SettlingAccountState(
            new_purchasing_power,
            copy.deepcopy(new_settling_account_state.ideal_account_state),
            new_settling_purgatory
        )
        changes.append((settlement_datetime, new_settling_account_state))

    # process order
    cash_before = new_settling_account_state.ideal_account_state.cash
    position_before = new_settling_account_state.ideal_account_state.positions.get(
        order.symbol, 0)
    new_account_state = apply_order_to_account_state(
        new_settling_account_state.ideal_account_state, order)
    cash_after = new_account_state.cash
    position_after = new_account_state.positions.get(order.symbol, 0)

    # depending on effect of order,
    # update purchasing power or add to settling purgatory
    diff = cash_after - cash_before

    # TODO: research settling for short positions
    if position_before < 0 or position_after < 0:
        logging.warn(
            f"Settling for short position is flawed, purchasing power is likely wrong")

    if diff < 0:  # money being used
        new_purchasing_power += diff  # deduct from purchasing power
    else:  # money being added
        # money is flowing in, schedule the cash to settle in the future
        # Options settle in 1 day: https://td.intelliresponse.com/tddirectinvesting/public/index.jsp?interfaceID=19&sessionId=921723fb-d96f-11ec-b911-43daeb48e13c&id=7551&requestType=&source=9&question=settled+
        # TODO: `1 or 2` better configuration needed(?)
        settlement_release_day = trading_day.n_trading_days_ahead(
            order.datetime.date(), 1 if order.is_option() else 2)
        settlement_release_datetime = typing.cast(
            datetime.datetime, trading_day.get_market_open_on_day(settlement_release_day))
        new_settling_purgatory = [
            (settlement_release_datetime, diff)] + new_settling_purgatory

    return changes + [(order.datetime, SettlingAccountState(
        new_purchasing_power,
        new_account_state,
        new_settling_purgatory
    ))]

#
# Account value estimation
#


class HolidayError(Exception):
    pass


def fetch_todays_close(symbol: str, date: datetime.date) -> float:
    candles = get_candles.get_d_candles(
        symbol, date, date)
    if not candles:  # it's a holiday, do not evaluate close on holidays
        raise HolidayError()
    return candles[-1]['close']


def evaluate_account_positions(account_state: IdealAccountState, date: datetime.date) -> dict[str, float]:
    return {symbol: size * fetch_todays_close(symbol, date) * (100 if symbol.startswith("O:") else 1) for symbol, size in account_state.positions.items()}


def evaluate_account_position_value(account_state: IdealAccountState, date: datetime.date) -> float:
    return sum(evaluate_account_positions(account_state, date).values())


def estimate_account_value(account_state: IdealAccountState, date: datetime.date) -> float:
    return account_state.cash + evaluate_account_position_value(account_state, date)


def simulate_account_every_close(changes: typing.Iterator[tuple[datetime.datetime, SettlingAccountState]]) -> typing.Iterable[typing.Tuple[datetime.datetime, SettlingAccountState]]:
    initial_change_dt, initial_change_state = next(changes)
    previous_dt = initial_change_dt

    previous_account_state = None

    for dt, account_state in itertools.chain([(initial_change_dt, initial_change_state)], changes):

        days_to_consider = trading_day.generate_trading_days(
            previous_dt.date(), dt.date())
        day_closes_to_consider = [typing.cast(
            datetime.datetime, trading_day.get_market_close_on_day(day)) for day in days_to_consider]
        day_closes_to_consider = [
            # >= and < reasoning: I want this to come after any change that happens at 4:00pm
            dt_close for dt_close in day_closes_to_consider if dt_close >= previous_dt and dt_close < dt]

        # ASSUMING no state should be yielded between 1st and 2nd change (no initial positions)
        if previous_account_state:
            for day_close in filter(lambda day_close: day_close < dt, day_closes_to_consider):
                yield day_close, previous_account_state

        # prepare for next iteration
        previous_dt = dt
        previous_account_state = account_state


def simulate_ideal_account(orders: typing.Iterator[types.FilledOrder], initial_account: IdealAccountState) -> typing.Iterator[typing.Tuple[types.FilledOrder, IdealAccountState]]:
    account = initial_account
    for order in orders:
        account = apply_order_to_account_state(account, order)
        yield order, account


def simulate_settling_account(orders: typing.Iterator[types.FilledOrder], initial_ideal_account: IdealAccountState) -> typing.Iterator[typing.Tuple[datetime.datetime, SettlingAccountState]]:
    initial_account = SettlingAccountState(
        0, initial_ideal_account, [])
    account = copy.deepcopy(initial_account)
    for order in orders:
        changes = apply_order_to_settling_account(
            account, order)
        for change in changes:
            dt, intermediate_account_state = change
            yield dt, intermediate_account_state
        account = changes[-1][1]

    # play out the rest of purgatory
    time_of_last_remaining_settlement = max(
        account.get_settling_purgatory())[0]
    remaining_settlement_changes = apply_order_to_settling_account(account, types.FilledOrder(
        intention=None, symbol="", quantity=0, price=0, datetime=time_of_last_remaining_settlement + datetime.timedelta(seconds=1)))
    for change in remaining_settlement_changes:
        dt, intermediate_account_state = change
        yield dt, intermediate_account_state


def value_at_close_every_day(settling_simulation: typing.Iterable[tuple[datetime.datetime, SettlingAccountState]]) -> typing.Iterator[typing.Tuple[datetime.date, float]]:
    for dt, account_state in simulate_account_every_close(iter(settling_simulation)):
        try:
            value = estimate_account_value(
                account_state.ideal_account_state, dt.date())
            yield dt.date(), value
        except HolidayError:
            # exclude holidays from valuation iterable
            # (so we actually get 252 trading days worth of valuation)
            pass


class Simulation:
    def __init__(self, states_by_date: list[tuple[datetime.datetime, SettlingAccountState]]):
        self._states_by_date = states_by_date

    @staticmethod
    def from_orders(orders: list[types.FilledOrder], initial_account: IdealAccountState):
        return Simulation(list(
            simulate_settling_account(iter(orders), initial_account)))

    def get_ideal_initial_balance(self) -> float:
        return -min(self._states_by_date, key=lambda t: t[1].get_purchasing_power())[
            1].get_purchasing_power()

    def get_final_pnl(self) -> float:
        final_state = self._states_by_date[-1]
        return estimate_account_value(final_state[1].ideal_account_state, final_state[0].date())

    def get_values(self) -> pd.Series:
        """Returns account value estimates by day"""
        end_of_day_values = list(
            value_at_close_every_day(self._states_by_date))
        start, _end = end_of_day_values[0][0], end_of_day_values[-1][0]
        returns = pd.Series(
            dict([(start - datetime.timedelta(days=1), 0.)] + end_of_day_values))
        returns = returns + \
            self.get_ideal_initial_balance()  # adjust for initial balance
        # switch to PD timestamps
        returns = pd.Series(returns.values, [
            pd.to_datetime(dt) for dt in returns.index])
        return returns

    def get_returns(self) -> pd.Series:
        """Returns percent returns by day"""
        return self.get_values().pct_change().dropna()


def settling_stats_for_orders(orders: list[types.FilledOrder], initial_account: IdealAccountState, risk_free_rate: float = 0.02) -> dict:
    # TODO: this is very geometric-oriented
    # TODO: make a script to adjust arithmetic trades (fixed shares or fixed value) to scale percentage-wise with portfolio
    stats = {}
    stats['orders'] = len(orders)

    simulation = Simulation.from_orders(orders, initial_account)

    # set initial balance to be just enough to make all purchases
    initial_balance = simulation.get_ideal_initial_balance()
    stats['initial_balance'] = initial_balance

    pnl = simulation.get_final_pnl()
    stats['pnl'] = pnl

    final_balance = pnl + initial_balance
    stats['final_balance'] = final_balance

    total_roi = pnl / initial_balance
    stats['total_roi'] = total_roi

    usage = sum(o.price * o.quantity for o in orders if o.is_buy())
    stats['usage'] = usage
    stats['huff_puff_ratio'] = pnl / usage
    # Idea: pnl is good, usage is bad because it represents risk and work and effort
    # So use it as a ratio like Sharpe or Sortino or whatever
    # Here, however, the units are different.
    # Not sure what good ranges are yet, but higher is better usually

    values = simulation.get_values()
    returns = values.pct_change()

    stats['quantstats'] = {}
    # stats['quantstats']['autocorr_penalty'] = quantstats.stats.autocorr_penalty(
    #     returns) # TODO: why returns NaN?
    stats['quantstats']['average_losing_day_roi'] = quantstats.stats.avg_loss(
        returns, 'day')
    stats['quantstats']['average_losing_week_roi'] = quantstats.stats.avg_loss(
        returns, 'week')
    stats['quantstats']['average_losing_month_roi'] = quantstats.stats.avg_loss(
        returns, 'month')
    stats['quantstats']['average_losing_quarter_roi'] = quantstats.stats.avg_loss(
        returns, 'quarter')
    stats['quantstats']['average_losing_year_roi'] = quantstats.stats.avg_loss(
        returns, 'year')
    stats['quantstats']['average_day_return'] = quantstats.stats.avg_return(
        returns, 'day')
    stats['quantstats']['average_week_return'] = quantstats.stats.avg_return(
        returns, 'week')
    stats['quantstats']['average_month_return'] = quantstats.stats.avg_return(
        returns, 'month')
    stats['quantstats']['average_quarter_return'] = quantstats.stats.avg_return(
        returns, 'quarter')
    stats['quantstats']['average_year_return'] = quantstats.stats.avg_return(
        returns, 'year')
    stats['quantstats']['average_winning_day_roi'] = quantstats.stats.avg_win(
        returns, 'day')
    stats['quantstats']['average_winning_week_roi'] = quantstats.stats.avg_win(
        returns, 'week')
    stats['quantstats']['average_winning_month_roi'] = quantstats.stats.avg_win(
        returns, 'month')
    stats['quantstats']['average_winning_quarter_roi'] = quantstats.stats.avg_win(
        returns, 'quarter')
    stats['quantstats']['average_winning_year_roi'] = quantstats.stats.avg_win(
        returns, 'year')
    stats['quantstats']['best_day_roi'] = quantstats.stats.best(
        returns, "day")
    stats['quantstats']['best_week_roi'] = quantstats.stats.best(
        returns, "week")
    stats['quantstats']['best_month_roi'] = quantstats.stats.best(
        returns, "month")
    stats['quantstats']['best_quarter_roi'] = quantstats.stats.best(
        returns, "quarter")
    stats['quantstats']['best_year_roi'] = quantstats.stats.best(
        returns, "year")
    stats['quantstats']['cagr'] = quantstats.stats.cagr(
        returns, rf=risk_free_rate)
    stats['quantstats']['calmar_ratio'] = quantstats.stats.calmar(
        returns)  # cagr / max drawdown
    stats['quantstats']['common_sense_ratio'] = quantstats.stats.common_sense_ratio(
        returns)  # profit factor * tail ratio (combined on-base and home-run stats)
    stats['quantstats']['compounded_returns_total'] = quantstats.stats.comp(
        returns)  # TODO: revisit; seems like total_roi, not sure where compounding comes in
    stats['quantstats']['conditional_value_at_risk'] = quantstats.stats.conditional_value_at_risk(
        returns)  # percent of portfolio at risk to big losses (95% confidence)
    # AKA cvar, expected_shortfall
    stats['quantstats']['consecutive_losing_days_max'] = quantstats.stats.consecutive_losses(
        returns, 'day')
    stats['quantstats']['consecutive_losing_weeks_max'] = quantstats.stats.consecutive_losses(
        returns, 'week')
    stats['quantstats']['consecutive_losing_months_max'] = quantstats.stats.consecutive_losses(
        returns, 'month')
    stats['quantstats']['consecutive_losing_quarters_max'] = quantstats.stats.consecutive_losses(
        returns, 'quarter')
    stats['quantstats']['consecutive_losing_years_max'] = quantstats.stats.consecutive_losses(
        returns, 'year')
    stats['quantstats']['consecutive_winning_days_max'] = quantstats.stats.consecutive_wins(
        returns, 'day')
    stats['quantstats']['consecutive_winning_weeks_max'] = quantstats.stats.consecutive_wins(
        returns, 'week')
    stats['quantstats']['consecutive_winning_months_max'] = quantstats.stats.consecutive_wins(
        returns, 'month')
    stats['quantstats']['consecutive_winning_quarters_max'] = quantstats.stats.consecutive_wins(
        returns, 'quarter')
    stats['quantstats']['consecutive_winning_years_max'] = quantstats.stats.consecutive_wins(
        returns, 'year')
    # stats['quantstats']['cpc_index'] = quantstats.stats.cpc_index(
    #     returns)  # TODO: what does this mean? (I know how to calc)
    # sounds like it's only useful in relation to itself

    # expected_return is same as geometric_mean, ghpr
    stats['quantstats']['expected_return_day'] = quantstats.stats.expected_return(
        returns, 'day')
    stats['quantstats']['expected_return_week'] = quantstats.stats.expected_return(
        returns, 'week')
    stats['quantstats']['expected_return_month'] = quantstats.stats.expected_return(
        returns, 'month')
    stats['quantstats']['expected_return_quarter'] = quantstats.stats.expected_return(
        returns, 'quarter')
    stats['quantstats']['expected_return_year'] = quantstats.stats.expected_return(
        returns, 'year')
    stats['quantstats']['exposure'] = quantstats.stats.exposure(
        returns)  # days we play (non-0 returns)
    stats['quantstats']['gain_to_pain_ratio'] = quantstats.stats.gain_to_pain_ratio(
        returns)  # sum(returns) / sum(losses)

    stats['quantstats']['kelly_criterion'] = quantstats.stats.kelly_criterion(
        returns)  # NOTE: sounds like this is flawed, quantfiction.com, he likes "Ideal f" a bit more
    # TODO: calculate "Ideal f"
    stats['quantstats']['kurtosis'] = quantstats.stats.kurtosis(
        returns)  # TODO: plot the distribution
    stats['quantstats']['max_drawdown'] = quantstats.stats.max_drawdown(
        returns)
    stats['quantstats']['outlier_loss_ratio'] = quantstats.stats.outlier_loss_ratio(
        returns)  # if 3, means 1st percentile losses are 3x worse than average loss. (high -> disasters)
    stats['quantstats']['outlier_win_ratio'] = quantstats.stats.outlier_win_ratio(
        returns)  # if 3, means 99th percentile wins are 3x bigger than average win. (high -> home runs)
    stats['quantstats']['payoff_ratio'] = quantstats.stats.payoff_ratio(
        returns)  # average win / average loss; aka win_loss_ratio
    stats['quantstats']['profit_factor'] = quantstats.stats.profit_factor(
        returns)  # sum(wins) / sum(losses); you want >1
    # stats['quantstats']['profit_ratio'] = quantstats.stats.profit_ratio(
    #     returns)  # TODO: why computes same as profit_factor?
    # stats['quantstats']['rar'] = quantstats.stats.rar(
    #     returns, rf=risk_free_rate)  # TODO: poorly explained?
    # stats['quantstats']['recovery_factor'] = quantstats.stats.recovery_factor(
    #     returns)  # TODO: poorly explained?
    stats['quantstats']['risk_of_ruin'] = quantstats.stats.risk_of_ruin(
        returns)  # probabiliy 0-1 (AKA 'ror')
    stats['quantstats']['risk_return_ratio'] = quantstats.stats.risk_return_ratio(
        returns)  # (sharpe sans risk-free-rate)
    stats['quantstats']['serenity_index'] = quantstats.stats.serenity_index(
        returns, rf=typing.cast(int, risk_free_rate))  # higher is better; returns / penalized risk
    # 16 https://www.keyquant.com/Download/GetFile?Filename=%5CPublications%5CKeyQuant_WhitePaper_APT_Part1.pdf
    # "better sharpe" (my words)
    stats['quantstats']['sharpe'] = quantstats.stats.sharpe(
        returns, rf=risk_free_rate)
    # returns / volatility (stddev of returns; not too helpful)
    stats['quantstats']['skew'] = quantstats.stats.skew(returns)
    # more skew means more crazy
    stats['quantstats']['smart_sharpe'] = quantstats.stats.smart_sharpe(
        returns, rf=risk_free_rate)  # weighs big drawdowns more
    # stats['quantstats']['smart_sortino'] = quantstats.stats.smart_sortino(
    #     returns, rf=typing.cast(int, risk_free_rate))
    #     # TODO: cannot find explanation for smart_sortino
    stats['quantstats']['sortino'] = quantstats.stats.sortino(
        returns, rf=typing.cast(int, risk_free_rate))
    # like sharpe but uses stddev of downside (not all returns);
    stats['quantstats']['tail_ratio'] = quantstats.stats.tail_ratio(
        returns)  # >1 means upside crazy is better than downside crazy
    stats['quantstats']['ulcer_index'] = quantstats.stats.ulcer_index(
        returns)  # lower is better for risk; 0-1. "quadratic mean of drawdowns"
    # Page 11-12 https://www.keyquant.com/Download/GetFile?Filename=%5CPublications%5CKeyQuant_WhitePaper_APT_Part1.pdf
    # stats['quantstats']['ulcer_performance_index'] = quantstats.stats.ulcer_performance_index(
    #     returns, rf=typing.cast(int, risk_free_rate))  # TODO: find explanation, none given
    stats['quantstats']['upi'] = quantstats.stats.upi(
        returns, rf=typing.cast(int, risk_free_rate))
    # sharpe-like but volatility=ulcer index (path-aware)
    stats['quantstats']['value_at_risk'] = quantstats.stats.value_at_risk(
        returns)  # % of investment at risk (95% confidence) on a given day
    # AKA var
    stats['quantstats']['volatility'] = quantstats.stats.volatility(
        returns)
    stats['quantstats']['win_rate_day'] = quantstats.stats.win_rate(
        returns, 'day')
    stats['quantstats']['win_rate_week'] = quantstats.stats.win_rate(
        returns, 'week')
    stats['quantstats']['win_rate_month'] = quantstats.stats.win_rate(
        returns, 'month')
    stats['quantstats']['win_rate_quarter'] = quantstats.stats.win_rate(
        returns, 'quarter')
    stats['quantstats']['win_rate_year'] = quantstats.stats.win_rate(
        returns, 'year')

    stats['quantstats']['worst_day_roi'] = quantstats.stats.worst(
        returns, 'day')
    stats['quantstats']['worst_week_roi'] = quantstats.stats.worst(
        returns, 'week')
    stats['quantstats']['worst_month_roi'] = quantstats.stats.worst(
        returns, 'month')
    stats['quantstats']['worst_quarter_roi'] = quantstats.stats.worst(
        returns, 'quarter')
    stats['quantstats']['worst_year_roi'] = quantstats.stats.worst(
        returns, 'year')

    # TODO: try plotting/playing with these
    # stats['quantstats']['to_drawdown_series'] = quantstats.stats.to_drawdown_series(returns)
    # stats['quantstats']['compsum'] = quantstats.stats.compsum(returns)
    # stats['quantstats']['distribution'] = quantstats.stats.distribution(
    #     returns)
    # stats['quantstats']['drawdown_details'] = quantstats.stats.drawdown_details(
    #     returns)
    # stats['quantstats']['implied_volatility'] = quantstats.stats.implied_volatility(
    #     returns) # all NaN
    # TODO: get this somewhere?
    # stats['quantstats']['monthly_returns'] = quantstats.stats.monthly_returns(
    #     returns)
    # stats['quantstats']['outliers'] = quantstats.stats.outliers(returns)
    # stats['quantstats']['remove_outliers'] = quantstats.stats.remove_outliers(
    #     returns)
    # stats['quantstats']['rolling_sharpe'] = quantstats.stats.rolling_sharpe(
    #     returns)
    # stats['quantstats']['rolling_sortino'] = quantstats.stats.rolling_sortino(
    #     returns)
    # stats['quantstats']['rolling_volatility'] = quantstats.stats.rolling_volatility(
    #     returns)
    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument("result_name", type=str)

    args = parser.parse_args()

    from src.results import read_results

    orders = list(read_results.get_orders(args.result_name))
    # simulation = Simulation.from_orders(
    #     orders, IdealAccountState.empty(build_td_simulation()))
    # simulation.get_values()
    pprint(settling_stats_for_orders(
        orders, IdealAccountState.empty(build_td_simulation())))

    # ideal_simulation = list(simulate_ideal_account(
    #     iter(orders), IdealAccountState.empty(simulation_parameters)))
    # ideal_initial_balance = - \
    #     min(ideal_simulation, key=lambda t: t[1].cash)[1].cash
    # ideal_pnl = estimate_account_value(
    #     ideal_simulation[-1][1], ideal_simulation[-1][0].datetime.date())

    # ideal_final_balance = ideal_initial_balance + ideal_pnl
    # print(
    #     f"Ideal:    initial={ideal_initial_balance:>8.2f} \tfinal={(ideal_final_balance):>8.2f} \tROI={ideal_pnl / ideal_initial_balance:>8.2%}")

    # pprint(settling_stats_for_orders(
    #     list(orders), IdealAccountState.empty(simulation_parameters)))
