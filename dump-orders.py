from datetime import datetime, timedelta, timezone
import os
from zoneinfo import ZoneInfo

from src.broker import get_filled_orders


MARKET_TZ = ZoneInfo("America/New_York")

start = datetime(2000, 1, 1)
end = datetime.now() + timedelta(days=1)

filled_orders = get_filled_orders(start, end)

HOME = os.environ['HOME']

# TODO: separate by environment
with open(f'{HOME}/filled-orders.csv', 'w') as f:
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
