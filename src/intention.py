from datetime import date
from zoneinfo import ZoneInfo

from src.broker.dry_run import DRY_RUN
from src.pathing import get_order_intentions_csv_path


MARKET_TZ = ZoneInfo("America/New_York")


def record_intentions(today: date, order_intentions: list, metadata: dict = {}):
    if DRY_RUN:
        print("DRY_RUN: not writing order intentions (may overwrite), instead writing to stdout")

    path = get_order_intentions_csv_path(today)
    f = open(path, 'w') if not DRY_RUN else None

    headers = ["Date", "Time", "Symbol", "Quantity", "Price", "Side"]
    for key in sorted(metadata.keys()):
        headers.append(key)

    print(",".join(headers), file=f)
    for order_intention in order_intentions:
        now = order_intention['datetime'].astimezone(MARKET_TZ)
        ticker = order_intention['symbol']
        quantity = order_intention['quantity']
        price = order_intention['price']
        side = order_intention['side']
        row = {
            "Date": now.strftime('%Y-%m-%d'),
            "Time": now.strftime('%H:%M:%S'),
            "Symbol": ticker,
            "Quantity": quantity,
            "Price": round(price, 4),
            "Side": side.upper(),
        }
        row.update(metadata)

        s = ",".join([str(row[key]) for key in headers])
        print(s, file=f)

    if f:
        f.close()
