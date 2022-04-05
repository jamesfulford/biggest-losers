from datetime import date, datetime
import os

from src.outputs.intention import log_intentions
from src.data.polygon.asset_class import is_stock

from src.strat.losers.logic import buy_biggest_losers, sell_biggest_losers_at_open
from src.trading_day import today_or_previous_trading_day


def get_env_var(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    print(f"{name} = '{value}'")
    return value


def get_biggest_loser_filter_criteria_kwargs():
    closing_price_min = float(get_env_var("CLOSING_PRICE_MIN", "0.0"))
    assert closing_price_min >= 0

    minimum_volume = int(get_env_var("MINIMUM_VOLUME", "0"))
    assert minimum_volume >= 0

    minimum_dollar_volume = int(
        get_env_var("MINIMUM_DOLLAR_VOLUME", "10000"))  # differs from stock
    assert minimum_dollar_volume >= 0

    top_n = int(get_env_var("TOP_N", "10"))
    assert top_n > 0

    cash_percent_to_use = float(get_env_var("CASH_PERCENT_TO_USE", ".33"))
    assert cash_percent_to_use <= 1
    assert cash_percent_to_use > 0

    return {
        "minimum_loss_percent": .1,
        "closing_price_min": closing_price_min,
        "minimum_volume": minimum_volume,
        "minimum_dollar_volume": minimum_dollar_volume,
        "top_n": top_n,
        "cash_percent_to_use": cash_percent_to_use,
    }


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
        strategy_name = "biggest_losers_stocks"
        filter_criteria_kwargs = get_biggest_loser_filter_criteria_kwargs()

        order_intentions = buy_biggest_losers(
            today,
            **filter_criteria_kwargs,
            warrant_criteria=lambda c: is_stock(c["T"], day=today),
        )
        log_intentions(strategy_name, order_intentions, metadata={
            **filter_criteria_kwargs,
            "git_commit": os.environ.get("GIT_COMMIT", ""),
        })
    elif action == 'sell':
        sell_biggest_losers_at_open(today)
