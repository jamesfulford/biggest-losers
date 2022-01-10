from datetime import timedelta
import json
import logging
from time import sleep
from http.client import HTTPConnection  # py3

import requests
from requests.models import HTTPError

from src.broker.alpaca import ALPACA_URL, APCA_HEADERS, sell_symbol_market
from src.finnhub import get_candles
from src.trading_day import (
    get_market_close_on_day,
    get_market_open_on_day,
    now,
    today,
    today_or_previous_trading_day,
)


# detailed HTTP debug logging
log = logging.getLogger("urllib3")  # works

log.setLevel(logging.DEBUG)  # needed
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
log.addHandler(ch)
HTTPConnection.debuglevel = 1

#
# Defining functions
#


def place_oto(
    symbol: str,
    quantity: int,
    take_profit_limit: float,
):
    body = {
        "side": "buy",
        "symbol": symbol,
        "type": "market",
        "qty": str(quantity),
        "time_in_force": "gtc",
        "order_class": "oto",
        "take_profit": {
            "limit_price": str(take_profit_limit),
        },
    }

    response = requests.post(
        ALPACA_URL + "/v2/orders",
        json=body,
        headers=APCA_HEADERS,
    )
    response.raise_for_status()
    return response.json()


def place_oco(
    symbol: str,
    quantity: int,
    take_profit_limit: float,
    stop_loss_stop: float,
    stop_loss_limit: float = None,
):
    body = {
        "side": "sell",
        "symbol": symbol,
        "type": "limit",
        "qty": str(quantity),
        "time_in_force": "gtc",
        "order_class": "oco",
        "take_profit": {"limit_price": str(take_profit_limit)},
        "stop_loss": {
            "stop_price": str(stop_loss_stop),
        },
    }
    if stop_loss_limit:
        body["stop_loss"]["limit_price"] = str(stop_loss_limit)

    response = requests.post(
        ALPACA_URL + "/v2/orders",
        json=body,
        headers=APCA_HEADERS,
    )
    response.raise_for_status()
    return response.json()


def cancel_order(order_id: str) -> None:
    response = requests.delete(
        ALPACA_URL + f"/v2/orders/{order_id}",
        headers=APCA_HEADERS,
    )
    response.raise_for_status()


def cancel_all_orders() -> None:
    response = requests.delete(
        ALPACA_URL + f"/v2/orders",
        headers=APCA_HEADERS,
    )
    response.raise_for_status()


def wait_until(t):
    while True:
        market_time = now()

        if market_time >= t:
            print(f"{t} is here")
            break

        seconds_remaining = (
            t - market_time
        ).seconds + 1  # so no crazy loop in last few milliseconds
        print(f"{market_time} is before {t}, waiting {seconds_remaining} seconds")

        sleep(min(seconds_remaining, 60))


def main():
    symbol = "NRGU"
    # TODO: get quantity by checking account balance
    quantity = 1
    take_profit_percentage = 0.1
    stop_loss_percentage = 0.005

    # 1: place OTO (one triggers other) -> Buy at open, set take_profit (upper bound)

    # 2: cancel take_profit part of OTO
    # 2.1: place OCO (one cancels other) -> stop_loss (lower bound), take_profit (upper bound)

    # 3: cancel OCO
    # 3.1: sell at market

    #
    # 1
    #

    # TODO: do market order early in morning, then get current_price from filled order
    # and then place limit order to be like take_profit

    market_today = today_or_previous_trading_day(
        today()
    )  # previous trading day for weekend code testing

    wait_until(get_market_open_on_day(market_today))
    sleep(5)  # make sure Finnhub has some candles

    # Get candles for today so we can set take_profit, stop_loss
    candles = get_candles(symbol, "D", market_today, market_today)
    current_price = candles[0]["close"]
    take_profit = current_price * (1 + take_profit_percentage)
    stop_loss = current_price * (1 - stop_loss_percentage)

    print("Placing order")
    first_order = place_oto(
        symbol,
        quantity,
        take_profit,
    )
    print(json.dumps(first_order, indent=2))
    first_order_leg_order_id = first_order["legs"][0]["id"]

    #
    # 2: Add on a stop_loss at 10am (if still in)
    #
    wait_until(get_market_open_on_day(market_today) + timedelta(minutes=30))

    # We want to add a stop loss.

    # Alpaca doesn't allow replacing OTO/Bracket orders (beyond changing stop/limit prices)
    # so, we need to cancel and create a new order

    print("Cancelling order")
    cancel_order(first_order_leg_order_id)

    # Confirmed with Alpaca:
    # if stop is already passed, placing the OCO will cause the stop to trigger immediately.

    print("Placing OCO")
    try:
        second_order = place_oco(
            symbol,
            quantity,
            take_profit_limit=take_profit,
            stop_loss_stop=stop_loss,
        )
        print(json.dumps(second_order, indent=2))
        second_order_leg_order_id = second_order["legs"][0]["id"]
    except HTTPError as e:
        # 'account is not allowed to short' -> no shares present
        # NOTE: account must be configured to not allow shorting, else we will short
        if e.response.status_code == 403 and e.response.json()["code"] == 40310000:
            print(
                "Shares not available (probably either hit take_profit or was not filled originally), cannot place OCO order.",
                e.response.json(),
            )
            return
        raise e

    #
    # 3: Close position near close (if still in)
    #
    wait_until(get_market_close_on_day(market_today) - timedelta(minutes=1))

    print("Cancelling brackets...")
    cancel_order(second_order_leg_order_id)

    print("Closing position...")
    try:
        sell_symbol_market(symbol, quantity)
    except HTTPError as e:
        if e.response.status_code == 403 and e.response.json()["code"] == 40310000:
            print(
                "Shares not available (hit take_profit or stop_loss), cannot place OCO order.",
                e.response.json(),
            )
            return
        raise e

    wait_until(get_market_close_on_day(market_today))


if __name__ == "__main__":
    try:
        main()
    except HTTPError as e:
        print("ERROR", e.response.status_code, e.response.json())
    finally:
        cancel_all_orders()
