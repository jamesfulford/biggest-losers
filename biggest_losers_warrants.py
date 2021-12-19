from datetime import date, datetime
import os

from src.intention import record_intentions
from src.criteria import is_warrant

from biggest_losers import buy_biggest_losers_at_close, sell_biggest_losers_at_open


if __name__ == '__main__':
    today = date.today()

    import sys

    # buy or sell logic
    action = sys.argv[1]
    valid_actions = ['buy', 'sell']
    if action not in valid_actions:
        print(f"invalid action, must be one of {valid_actions}")
        exit(1)

    # allow reading `today` from CLI $2
    datestr = ""
    try:
        datestr = sys.argv[2]
    except:
        pass

    if datestr:
        try:
            today = datetime.strptime(datestr, '%Y-%m-%d').date()
        except Exception as e:
            print(
                f"error occurred while parsing datetime, will continue with {today}", e)

    print(f"running on date {today} with action {action}")

    if action == 'buy':
        strategy_name = "biggest_losers_warrants"
        minimum_loss_percent = 0.1
        closing_price_min = 0.0
        minimum_volume = 0
        top_n = 10
        cash_percent_to_use = 0.9

        order_intentions = buy_biggest_losers_at_close(
            today,
            minimum_loss_percent=minimum_loss_percent,
            closing_price_min=closing_price_min,
            minimum_volume=minimum_volume,
            top_n=top_n,
            warrant_criteria=lambda c: is_warrant(c["T"]),
            cash_percent_to_use=cash_percent_to_use,
        )
        # write order intentions to file so we can evaluate slippage later
        record_intentions(today, order_intentions, metadata={
            "strategy_name": strategy_name,
            "minimum_loss_percent": minimum_loss_percent,
            "closing_price_min": closing_price_min,
            "minimum_volume": minimum_volume,
            "top_n": top_n,
            "cash_percent_to_use": cash_percent_to_use,
            "git_commit": os.environ.get("GIT_COMMIT", ""),
        })
    elif action == 'sell':
        sell_biggest_losers_at_open(today)
