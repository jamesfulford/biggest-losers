import json

from requests.models import HTTPError

from src.broker.alpaca import (cancel_order, get_positions,
                               place_oco)
from src.trading_day import now
from src.wait import wait_until


def execute_brackets(brackets: list, base_price: float, symbol: str, quantity: int):
    _execute_brackets(brackets, base_price, symbol, quantity)

    position = next(
        filter(lambda p: p["symbol"] == symbol, get_positions()), None)
    return position


def _execute_brackets(brackets: list, base_price: float, symbol: str, quantity: int):
    previous_oco_order_id = None
    for bracket in brackets:

        # if we are starting mid-day, fast-forward to the current bracket
        if bracket["until"] < now():
            continue

        take_profit_percentage = bracket["take_profit_percentage"]
        stop_loss_percentage = bracket["stop_loss_percentage"]

        take_profit = round(base_price * (1 + take_profit_percentage), 2)
        stop_loss = round(base_price * (1 - stop_loss_percentage), 2)
        print(f"Intended brackets: ({stop_loss}, {take_profit})")

        if previous_oco_order_id:
            print("Cancelling previous OCO order...")
            cancel_order(previous_oco_order_id)

        try:
            order = place_oco(
                symbol,
                quantity,
                take_profit_limit=take_profit,
                stop_loss_stop=stop_loss,
            )
            print(json.dumps(order, indent=2))
            previous_oco_order_id = order["legs"][0]["id"]
        except HTTPError as e:
            # 'account is not allowed to short' -> no shares present
            # NOTE: account must be configured to not allow shorting, else we may short
            if e.response.status_code == 403 and e.response.json()["code"] == 40310000:
                print(
                    "Shares not available (likely hit take_profit or stop_loss or was not filled originally), cannot place OCO order.",
                    e.response.json(),
                )
                return
            raise e

        until = bracket["until"]
        wait_until(until)

    if previous_oco_order_id:
        print("Cancelling previous OCO order...")
        cancel_order(previous_oco_order_id)
