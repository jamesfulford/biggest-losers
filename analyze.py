from datetime import datetime
from src.trades import get_closed_trades


trades = list(get_closed_trades(datetime(2021, 12, 6), datetime.now()))

# total
change = 0
used_cash = 0
for trade in trades:
    change += trade["profit_loss"]
    used_cash += trade["bought_cost"]

print()
print(
    f"Total change: {round(change, 2)} ({round(100 * change / used_cash, 1)}%)")
print()

# by day
trades_by_closed_day = {}

for trade in trades:
    key = trade["closed_at"].date().isoformat()
    trades_by_closed_day[key] = trades_by_closed_day.get(key, []) + [trade]

today = datetime.now().date()
for day, trades_on_day in trades_by_closed_day.items():
    change = 0
    used_cash = 0
    for trade in trades:
        change += trade["profit_loss"]
        used_cash += trade["bought_cost"]
    print(f"{day}: {round(change, 2)} ({round(100 * change / used_cash, 1)}%)")

    if today == trade["closed_at"].date():
        print()
        print("Today's trading results:")
        for trade in trades:
            profit_loss = round(trade["profit_loss"], 2)
            profit_loss_str = str(profit_loss)
            decimal_places = len(profit_loss_str.split(".")[-1])
            profit_loss_str = profit_loss_str + "0" * (2 - decimal_places)

            print(trade["symbol"].rjust(8),
                  profit_loss_str.rjust(10), str(round(100 * trade["roi"], 1)).rjust(6) + "%")
