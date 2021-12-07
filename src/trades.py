from datetime import datetime

from src.broker import get_filled_orders


def build_trade(trade_orders):
    # NOTE: this function assumes every buy has 1 sell and no overlapping trades for same symbol.
    symbol = trade_orders[0]["symbol"]

    # assume all orders are for same symbol
    # this logic assumes first order is buy and last order is sell and no other orders occured for this symbol in this time
    if len(trade_orders) > 2:
        print(
            f'WARNING: more than 2 orders for symbol {symbol} detected, skipping')
        return

    buy_order = trade_orders[0]
    sell_order = trade_orders[-1]

    if buy_order["side"] != 'buy':
        print(
            f'WARNING: first order for {symbol} is not a buy, skipping')
        return

    if sell_order["side"] != 'sell':
        print(
            f'WARNING: last order for {symbol} is not a sell, skipping')
        return

    quantity = float(buy_order["filled_qty"])
    bought_price = float(buy_order["filled_avg_price"])
    sold_price = float(sell_order["filled_avg_price"])

    return {
        "symbol": symbol,
        "opened_at": datetime.strptime(buy_order["filled_at"], '%Y-%m-%dT%H:%M:%S.%fZ'),
        "closed_at": datetime.strptime(sell_order["filled_at"], '%Y-%m-%dT%H:%M:%S.%fZ'),
        # "orders": trade_orders,

        "quantity": quantity,
        "bought_cost": quantity * bought_price,
        "sold_cost": quantity * sold_price,

        "bought_price": bought_price,
        "sold_price": sold_price,

        "price_difference": sold_price - bought_price,
        "profit_loss": quantity * (sold_price - bought_price),

        "roi": (sold_price - bought_price) / bought_price,
        "is_win": sold_price > bought_price,
    }


def get_closed_trades(start, end, build_trade=build_trade):
    # group orders by symbol, then build trades for each set of orders that bring quantity to 0
    filled_orders = get_filled_orders(start, end)
    for trade_orders in group_orders_by_trade(filled_orders):
        trade = build_trade(trade_orders)
        if not trade:
            continue
        yield trade


def group_orders_by_trade(filled_orders):
    orders_by_symbol = {}
    for order in filled_orders:  # latest last
        orders_by_symbol[order["symbol"]] = orders_by_symbol.get(
            order["symbol"], []) + [order]

    for orders in orders_by_symbol.values():
        current_qty = 0
        index_of_last_trade = 0
        for i in range(len(orders)):
            order = orders[i]

            filled_qty = int(order["filled_qty"])
            qty_diff = filled_qty if order["side"] == 'buy' else -filled_qty

            current_qty += qty_diff
            if current_qty == 0:

                # before : is inclusive, after : is exclusive
                trade_orders = orders[index_of_last_trade:i + 1]
                index_of_last_trade = i + 1

                yield trade_orders

        # NOTE: open trades are not yielded
