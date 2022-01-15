from datetime import date, datetime
import os

from src.intention import record_intentions
from src.criteria import is_warrant
from src.broker.generic import buy_symbol_market

from src.biggest_losers import buy_biggest_losers, sell_biggest_losers_at_open
from src.trading_day import today_or_previous_trading_day


#
# NOTE:
# this is nearly identical to biggest_losers_stocks.py with these changes:
# 1. only warrants are considered
# 2. market orders, not market_on_close orders, are submitted
#
if __name__ == '__main__':
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
        # TODO: read from config
        minimum_loss_percent = 0.1
        closing_price_min = 0.0
        minimum_volume = 0
        minimum_dollar_volume = 10000
        top_n = 10
        cash_percent_to_use = float(
            os.environ.get("CASH_PERCENT_TO_USE", ".33"))
        print(cash_percent_to_use)

        order_intentions = buy_biggest_losers(
            today,
            minimum_loss_percent=minimum_loss_percent,
            closing_price_min=closing_price_min,
            minimum_volume=minimum_volume,
            minimum_dollar_volume=minimum_dollar_volume,
            top_n=top_n,
            warrant_criteria=lambda c: is_warrant(c["T"]),
            cash_percent_to_use=cash_percent_to_use,
            # Buys with market order, not at close
            buy_function=lambda symbol, quantity: buy_symbol_market(
                symbol, quantity),
        )
        # write order intentions to file so we can evaluate slippage later
        record_intentions(today, order_intentions, metadata={
            "strategy_name": strategy_name,
            "minimum_loss_percent": minimum_loss_percent,
            "closing_price_min": closing_price_min,
            "minimum_volume": minimum_volume,
            "minimum_dollar_volume": minimum_dollar_volume,
            "top_n": top_n,
            "cash_percent_to_use": cash_percent_to_use,
            "git_commit": os.environ.get("GIT_COMMIT", ""),
        })
    elif action == 'sell':
        sell_biggest_losers_at_open(today)
