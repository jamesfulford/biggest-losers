from datetime import date, datetime
import os
from src.strat.losers.stocks import get_biggest_loser_filter_criteria_kwargs

from src.intention import record_intentions
from src.criteria import is_warrant
from src.broker.generic import buy_symbol_market

from src.strat.losers.logic import buy_biggest_losers, sell_biggest_losers_at_open
from src.trading_day import today_or_previous_trading_day


#
# NOTE:
# this is nearly identical to src.strat.losers.stocks.py with these changes:
# 1. only warrants are considered
# 2. buy: market orders, not market_on_close orders
# 3. minimum dollar volume requirement
#
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("buy", "sell"))
    parser.add_argument(
        "--today", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date())

    args = parser.parse_args()

    action = args.action
    today = today_or_previous_trading_day(args.today or date.today())

    print(f"running on date {today} with action {action}")

    if action == 'buy':
        strategy_name = "biggest_losers_warrants"
        filter_criteria_kwargs = get_biggest_loser_filter_criteria_kwargs()
        filter_criteria_kwargs["minimum_dollar_volume"] = max(
            filter_criteria_kwargs["minimum_dollar_volume"], 10000)

        order_intentions = buy_biggest_losers(
            today,
            **filter_criteria_kwargs,

            warrant_criteria=lambda c: is_warrant(c["T"], day=today),
            # Buys with market order, not at close
            buy_function=lambda symbol, quantity: buy_symbol_market(
                symbol, quantity),
        )
        record_intentions(today, order_intentions, metadata={
            "strategy_name": strategy_name,
            **filter_criteria_kwargs,
            "git_commit": os.environ.get("GIT_COMMIT", ""),
        })
    elif action == 'sell':
        sell_biggest_losers_at_open(today)
