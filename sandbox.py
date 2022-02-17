from src.data.finnhub.finnhub import get_candles
from datetime import date
import ta
import pandas as pd


def get_dpo(candles, window=20):
    closes = pd.Series(list(map(lambda c: float(c["close"]), candles)))
    values = ta.trend.dpo(closes, window=window)
    value = float(values.values[-1])
    return value


candles = get_candles("NRGU", "D", date(2021, 2, 20), date(2022, 1, 1))
get_dpo(candles)
print(ta.trend.dpo.__doc__)
exit()


print(json.dumps(_get_alpaca("/v2/account"), indent=4))

exit()

orders = _get_alpaca("/v2/orders?status=closed")

orders = list(filter(lambda o: o["symbol"] == "NRGU", orders))


buy_orders = list(filter(lambda o: o["side"] == "buy", orders))
sell_orders = list(filter(lambda o: o["side"] == "sell", orders))

money_usage = 0
balance = 0
for buy_order in buy_orders:
    m = float(buy_order["filled_avg_price"]) * float(buy_order["filled_qty"])
    balance -= m
    money_usage += m

for sell_order in sell_orders:
    m = float(sell_order["filled_avg_price"]) * float(sell_order["filled_qty"])
    balance += m


positions = _get_alpaca("/v2/positions")
position = next(filter(lambda p: p["symbol"] == "NRGU", positions), None)
if position:
    balance += float(position["market_value"]) * float(position["qty"])

print(f"{balance=} {money_usage=} {balance/money_usage:.2%}")

# print(json.dumps(orders, indent=2), len(orders))


# rois = []

# days = 252
# win_rate = .98

# for i in range(int(days * win_rate)):
#     rois.append(1.01)


# for i in range(int(days * (1 - win_rate))):
#     rois.append(.9)

# current_balance = 1
# for roi in rois:
#     current_balance *= roi
# print(current_balance)
