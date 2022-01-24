from datetime import timedelta

from requests.models import HTTPError
from src.strat.brackets.brackets_realtime import execute_brackets

from src.broker.alpaca import (
    buy_symbol_market,
    sell_symbol_market,
    wait_until_order_filled,
)
from src.trading_day import (
    get_market_close_on_day,
    get_market_open_on_day,
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

    market_today = today_or_previous_trading_day(today())

    brackets = [
        {
            "take_profit_percentage": 0.1,
            "stop_loss_percentage": 0.25,  # unusually low please
            "until": get_market_open_on_day(market_today) + timedelta(minutes=30),
        },
        {
            "take_profit_percentage": 0.1,
            "stop_loss_percentage": 0.005,
            "until": get_market_close_on_day(market_today) - timedelta(minutes=1),
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
    print(f"Order filled. {filled_price=:.2f}, {quantity=}")

    #
    # 2: brackets
    #
    # TODO: set lower brackets based off of VWAP or an EMA or something
    # TODO: consider updating OCO regularly with new prices (based off of polling or websocket)
    position = execute_brackets(brackets, filled_price, symbol, quantity)
    if not position:
        return
    #
    # 3: timebox exit
    #
    print("Closing position...")
    sell_symbol_market(symbol, position["qty"])
