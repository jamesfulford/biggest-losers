import requests
import logging
from src.broker.generic import get_positions, place_oco


def place_ocos(up: float, down: float, positions=None):
    if positions is None:
        positions = get_positions()

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


def place_oco_for_position(position: dict, up: float, down: float) -> None:
    print(position)
    place_oco(position["symbol"], position["qty"],
              position['avg_price'] * up, position['avg_price'] * down)
