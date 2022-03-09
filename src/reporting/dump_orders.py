from datetime import datetime, timedelta
import logging
import sys

from src.broker.generic import get_filled_orders
from src.pathing import get_paths


def main():
    target_environment_name = next(
        filter(lambda s: not s.startswith("-"), sys.argv), None)

    start = datetime(2022, 1, 1)
    end = datetime.now() + timedelta(days=10)

    logging.info(
        f"Dumping filled orders in {target_environment_name=} ({start} to {end})...")

    filled_orders = get_filled_orders(start, end)

    path = get_paths(target_environment_name)[
        "data"]["outputs"]["filled_orders_csv"]
    with open(path, "w") as f:
        f.write("Date,Time,Symbol,Quantity,Price,Side\n")
        for order in filled_orders:
            now = order["filled_at"]
            ticker = order["symbol"]
            quantity = order["filled_qty"]
            price = order["filled_avg_price"]
            side = order["side"]
            s = f"{now.strftime('%Y-%m-%d')},{now.strftime('%H:%M:%S')},{ticker},{quantity},{price},{side.upper()}\n"
            f.write(s)

    logging.info(f"Done. Wrote {len(filled_orders)} orders to {path}")
