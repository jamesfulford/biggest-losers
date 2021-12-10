from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import sys

from src.broker import get_filled_orders
from src.pathing import get_paths


target_environment_name = sys.argv[1]


MARKET_TZ = ZoneInfo("America/New_York")

start = datetime(2000, 1, 1)
end = datetime.now() + timedelta(days=1)

filled_orders = get_filled_orders(start, end)

path = get_paths(target_environment_name)[
    'data']["outputs"]["filled_orders_csv"]
with open(path, 'w') as f:
    f.write("Date,Time,Symbol,Quantity,Price,Side\n")
    for order in filled_orders:
        now = datetime.strptime(
            order['filled_at'], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).astimezone(MARKET_TZ)
        ticker = order['symbol']
        quantity = order['filled_qty']
        price = order['filled_avg_price']
        side = order['side']
        s = f"{now.strftime('%Y-%m-%d')},{now.strftime('%H:%M:%S')},{ticker},{quantity},{price},{side.upper()}\n"
        f.write(s)
