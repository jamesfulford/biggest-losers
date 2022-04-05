import requests
import logging
import math
from src.broker.generic import get_positions, place_oco, get_open_orders


def place_ocos(up: float, down: float, positions=None):
    if positions is None:
        positions = get_positions()

    if not positions:
        return

    open_orders = get_open_orders()
    symbols_with_open_sell_orders = set(
        [order['symbol'] for order in open_orders if order['side'] == 'sell'])

    positions = list(
        filter(lambda p: p['symbol'] not in symbols_with_open_sell_orders, positions))

    if not positions:
        return

    logging.info(
        f"Placing OCOs ({up-1:.1%} up, {1-down:.1%} down) for {len(positions)} positions...")

    for position in positions:
        try:
            place_oco_for_position(position, up, down)
        except requests.exceptions.HTTPError as e:
            logging.exception(
                f"Failed to place order for {position['symbol']}: {e.response.text}, continuing...")

            # Alpaca logic:
            # if e.response.status_code == 403 and e.response.json()['code'] == 40310000:
            #     # insufficient qty available for order (requested: 1, available: 0)
            #     logging.warning(
            #         f"Failed to place order for {position['symbol']} (likely due to pre-existing order): {e.response.json()['message']}, continuing...")
            # else:

            # TD defers processing of order
            # - if order is placed and price has moved below stop, order is rejected by TD

    logging.info("Done placing OCOs.")


def round_up(price: float) -> float:
    if price > 1:
        price = price * 100
        return (math.ceil(price))/100
    else:
        price = price * 10_000
        return (math.ceil(price))/10_000


def round_down(price: float) -> float:
    if price > 1:
        price = price * 100
        return (math.floor(price))/100
    else:
        price = price * 10_000
        return (math.floor(price))/10_000


def place_oco_for_position(position: dict, up: float, down: float) -> None:

    place_oco(position["symbol"], position["qty"],
              round_up(position['avg_price'] * up), round_down(position['avg_price'] * down))
