from itertools import chain
import json

from requests.models import HTTPError

from src.trading_day import now
from src.wait import wait_until

from src.broker.alpaca import (
    buy_symbol_market,
    cancel_order,
    get_positions,
    place_oco,
    sell_symbol_market,
    wait_until_order_filled,
)
from src.trading_day import (
    get_market_close_on_day,
    get_market_open_on_day,
    now,
    today,
    today_or_previous_trading_day,
)


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

#
# Backtesting
#


def backtest_brackets(candles: list, brackets: list, base_price: float):
    """
    Returns sell_price, candle sold on, and bracket during which close occurred
    If no sale occurred, returns None, last candle in brackets, and last bracket in candles

    Caller must handle:
    - timeframing/timeboxing (only pass candles in desired time frame)
    - position entry (pass base_price for calculating percentage limits)
    - timebox exit (if stops/limits not hit and run out of brackets/candles)
    """
    candles = chain(candles)
    brackets = chain(brackets)

    candle = next(candles)
    bracket = next(brackets)

    try:
        while True:  # will escape because of `next` calls throwing StopIteration
            if candle["datetime"] >= bracket["until"]:
                bracket = next(brackets)

            take_profit = (1 + bracket["take_profit_percentage"]) * base_price
            stop_loss = (1 - bracket["stop_loss_percentage"]) * base_price

            is_stop_loss = candle["low"] < stop_loss
            is_take_profit = candle["high"] > take_profit

            if is_stop_loss:
                return stop_loss, candle, bracket
            if is_take_profit:
                return take_profit, candle, bracket

            candle = next(candles)
    except StopIteration:
        pass

    return None, candle, bracket
