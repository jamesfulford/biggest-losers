from datetime import timedelta
import json

from requests.models import HTTPError

from src.broker.alpaca import (
    buy_symbol_market,
    cancel_order,
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
from src.wait import wait_until


def main():
    symbol = "NRGU"

    # 1: place market order pre-market
    # 1.1: wait until market opens (if not already) (less polling to check order status)
    # 1.2: wait until order is filled

    # 2: place OCO order using percents of filled_avg_price (finish if position is closed)
    # 2.1: wait until market_open + `until`
    # 2.2: cancel current OCO order (if any)
    # 2.3: re-run step 2 for next set of brackets, until no brackets left

    # 3: cancel current OCO order
    # 3.1: close position using market orders (if any)

    market_today = today_or_previous_trading_day(
        today()
    )  # previous trading day for weekend code testing
    market_open = get_market_open_on_day(market_today)
    market_close = get_market_close_on_day(market_today)

    bracketing = [
        {
            "take_profit_percentage": 0.1,
            "stop_loss_percentage": 0.25,  # unusually low please
            "until": market_open + timedelta(minutes=30),
        },
        {
            "take_profit_percentage": 0.1,
            "stop_loss_percentage": 0.005,
            "until": market_close - timedelta(minutes=1),
        },
    ]

    #
    # 1: market-order entry
    #

    # TODO: do nominal Alpaca order with percentage of current balance
    # (for other brokers, use current_price from FinnHub and do nominal calculation on our side)
    entry_order = buy_symbol_market(symbol, 1)

    wait_until(get_market_open_on_day(market_today))

    print("Waiting for filled order...")
    filled_entry_order = wait_until_order_filled(entry_order["id"])
    filled_price = float(filled_entry_order["filled_avg_price"])
    quantity = int(filled_entry_order["filled_qty"])
    print(f"Order filled. price={filled_price}, quantity={quantity}")

    #
    # 2: brackets
    #

    previous_oco_order_id = None
    for bracket in bracketing:

        # if we are starting mid-day, fast-forward to the current bracket
        if bracket["until"] < now():
            continue

        take_profit_percentage = bracket["take_profit_percentage"]
        stop_loss_percentage = bracket["stop_loss_percentage"]

        take_profit = round(filled_price * (1 + take_profit_percentage), 2)
        stop_loss = round(filled_price * (1 - stop_loss_percentage), 2)
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

    #
    # 3: timebox exit
    #

    if previous_oco_order_id:
        print("Cancelling previous OCO order...")
        cancel_order(previous_oco_order_id)

    print("Closing position...")
    try:
        # TODO: if partial fills in any OCOs, we may have issues closing position
        sell_symbol_market(symbol, quantity)
    except HTTPError as e:
        if e.response.status_code == 403 and e.response.json()["code"] == 40310000:
            print(
                "Shares not available (likely hit take_profit or stop_loss or was not filled originally), cannot place OCO order.",
                e.response.json(),
            )
            return
        raise e


if __name__ == "__main__":
    try:
        main()
    except HTTPError as e:
        print("ERROR", e.response.status_code, e.response.json())
