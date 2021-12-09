from datetime import datetime
from src.pathing import get_paths
from src.trades import get_closed_trades_from_orders_csv


path = get_paths()['data']["outputs"]["filled_orders_csv"]
trades = list(get_closed_trades_from_orders_csv(path))

# by day
trades_by_closed_day = {}

for trade in trades:
    key = trade["closed_at"].date().isoformat()
    trades_by_closed_day[key] = trades_by_closed_day.get(key, []) + [trade]

total_change = 0
rois = []
today = datetime.now().date()
for day, trades_on_day in trades_by_closed_day.items():
    change = 0
    used_cash = 0
    for trade in trades_on_day:
        change += trade["profit_loss"]
        used_cash += trade["bought_cost"]

    roi = change / used_cash
    print(f"{day}: {round(change, 2)} ({round(100 * roi, 1)}%)")

    total_change += change
    rois.append(roi)

    if today == trades_on_day[0]["closed_at"].date():
        print()
        print(f"Today's trading results:")
        for trade in sorted(trades_on_day, key=lambda t: t["profit_loss"]):
            profit_loss = round(trade["profit_loss"], 2)
            profit_loss_str = str(profit_loss)
            decimal_places = len(profit_loss_str.split(".")[-1])
            profit_loss_str = profit_loss_str + "0" * (2 - decimal_places)

            print(trade["symbol"].rjust(8),
                  profit_loss_str.rjust(10), str(round(100 * trade["roi"], 1)).rjust(6) + "%")

print()


def g_avg(l):
    m = 1
    for i in l:
        m *= i
    return m ** (1/len(l))


geo_roi = g_avg(rois)
print(f"Total: {round(total_change, 2)}")
print(f"  days: {len(trades_by_closed_day)}")
print(f"  daily average: {round(100 * geo_roi, 1)}%")

annualized_roi = ((1 + geo_roi) ** 250) - 1
print(
    f"  annual roi: {round(100 * annualized_roi, 1)}% ({round(annualized_roi + 1, 1)}x)")
