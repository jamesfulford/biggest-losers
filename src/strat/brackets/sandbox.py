from datetime import date
from src.data.polygon.get_candles import get_candles

candles = get_candles("NRGU", "D", date(2021, 1, 1), date(2021, 12, 31))


rois = []
for candle in candles:

    buy_price = candle["open"]

    limit_price = candle["open"] * 1.01
    stop_price = candle["open"] * 0.5

    hit_limit = candle["high"] > limit_price
    hit_stop = candle["low"] < stop_price

    sell_price = candle["close"]
    if hit_limit:
        sell_price = limit_price
    if hit_stop:
        sell_price = stop_price

    if hit_limit and hit_stop:
        print(f"{candle['date']} AHAHAH {candle}")

    roi = (sell_price - buy_price) / buy_price

    # print(
    #     f"{candle['date']}\t{roi:.1%}\t{roi > 0}")
    rois.append(roi)


current_balance = 1
for roi in rois:
    current_balance *= 1+roi
print(current_balance)

print(sum(list(map(lambda roi: roi > 0, rois))) / len(rois))
