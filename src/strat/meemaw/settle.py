from datetime import datetime, timedelta
import logging
import sys
from time import sleep
from typing import Union
from src.broker.generic import get_open_orders
from src.trading_day import now


def await_buy_order_settling(symbols: Union[set, list, None] = None, deadline: Union[datetime, None] = None) -> None:
    def criteria(o): return o['side'] == 'BUY'
    if symbols:
        def criteria(o): return o['side'] == 'BUY' and o['symbol'] in symbols
    _await_order_settling(criteria, deadline)


def await_sell_order_settling(symbols: Union[set, list, None] = None, deadline: Union[datetime, None] = None) -> None:
    def criteria(o): return o['side'] == 'SELL'
    if symbols:
        def criteria(o): return o['side'] == 'SELL' and o['symbol'] in symbols
    _await_order_settling(criteria, deadline)


def _await_order_settling(is_order_not_ready, deadline: Union[datetime, None] = None) -> None:
    if not deadline:
        deadline = now() + timedelta(seconds=10)

    while now() < deadline:
        open_orders = get_open_orders()
        open_orders = [o for o in open_orders if is_order_not_ready(o)]
        if not open_orders:
            return

        logging.info(
            f"Waiting for {len(open_orders)} orders to complete ({[o['symbol'] for o in open_orders]})")
        sleep(1)

    raise TimeoutError(f"Timed out waiting for orders to settle")


def main():
    await_buy_order_settling(sys.argv[1:])
