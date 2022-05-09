from datetime import datetime
import logging
import typing
from zoneinfo import ZoneInfo

from src.outputs.jsonl_dump import read_jsonl_lines


class Order(typing.TypedDict):
    symbol: str
    datetime: datetime
    quantity: float
    is_long: bool

    # + and is_long=True : entered long  position
    # - and is_long=True : exited  long  position

    # - and is_long=False: entered short position
    # + and is_long=False: exited  short position

    # if is short, then entering is negative


class Trade(typing.TypedDict):
    symbol: str

    opened_at: datetime
    closed_at: datetime
    quantity: float

    bought_price: float  # average
    sold_price: float    # average

    # TODO: make these computed fields
    bought_cost: float
    sold_cost: float
    price_difference: float
    profit_loss: float
    roi: float
    is_win: bool


class SimpleTrade(Trade):
    pass


def get_virtual_orders_of_simple_trade(trade: SimpleTrade) -> typing.Tuple[Order, Order]:
    symbol = trade["symbol"]
    is_long = trade['quantity'] > 0
    entry: Order = {
        "symbol": symbol,
        "datetime": trade["opened_at"],
        # if it is short, then quantity is negative
        "quantity": trade["quantity"],
        "is_long": is_long,
    }
    ex_t: Order = {
        "symbol": symbol,
        "datetime": trade["closed_at"],
        # if it is long, then quantity is negative
        "quantity": -trade["quantity"],
        "is_long": is_long,
    }
    return entry, ex_t


def read_trades(path: str) -> typing.Iterator[Trade]:
    for d in read_jsonl_lines(path):
        trade = {
            "symbol": d["symbol"],

            "opened_at": datetime.fromisoformat(d["opened_at"]),
            "closed_at": datetime.fromisoformat(d["closed_at"]),
            "quantity": float(d["quantity"]),
            # TODO: bought_cost being negative doesn't make sense for short/put trades
            "bought_cost": round(float(d["bought_cost"]), 4),
            "sold_cost": round(float(d["sold_cost"]), 4),
            "bought_price": round(float(d["bought_price"]), 4),
            "sold_price": round(float(d["sold_price"]), 4),
            "price_difference": round(float(d["price_difference"]), 4),
            "profit_loss": round(float(d["profit_loss"]), 4),
            "roi": round(float(d["roi"]), 4),
            "is_win": bool(d["is_win"]),
        }
        yield typing.cast(Trade, trade)


def build_trade(trade_orders: list) -> typing.Optional[Trade]:
    # NOTE: this function assumes every buy has 1 sell and no overlapping trades for same symbol.
    symbol = trade_orders[0]["symbol"]

    # assume all orders are for same symbol
    # this logic assumes first order is buy and last order is sell and no other orders occured for this symbol in this time
    if len(trade_orders) > 2:
        logging.warning(
            f'more than 2 orders for symbol {symbol} detected, skipping')
        return

    buy_order = trade_orders[0]
    sell_order = trade_orders[-1]

    if buy_order["side"] != 'buy':
        logging.warning(
            f'first order for {symbol} is not a buy, skipping')
        return

    if sell_order["side"] != 'sell':
        logging.warning(
            f'last order for {symbol} is not a sell, skipping')
        return

    quantity = float(buy_order["quantity"])
    bought_price = float(buy_order["price"])
    sold_price = float(sell_order["price"])

    return {
        "symbol": symbol,
        "opened_at": buy_order["datetime"],
        "closed_at": sell_order["datetime"],

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


MARKET_TZ = ZoneInfo("America/New_York")


def get_filled_orders_from_csv(path):
    lines = []
    with open(path, "r") as f:
        lines.extend(f.readlines())

    headers = lines[0].strip().split(",")

    # remove newlines and header row
    lines = [l.strip() for l in lines[1:]]

    # convert to dicts
    raw_dict_lines = [dict(zip(headers, l.strip().split(","))) for l in lines]

    lines = [{
        "datetime": datetime.strptime(l["Date"] + " " + l["Time"], '%Y-%m-%d %H:%M:%S').astimezone(MARKET_TZ),
        "symbol": l["Symbol"],
        "quantity": float(l["Quantity"]),
        "price": float(l["Price"]),
        "side": l["Side"].lower(),
    } for l in raw_dict_lines]

    return lines


def get_closed_trades_from_orders_csv(path, build_trade=build_trade) -> typing.Iterable[Trade]:
    filled_orders = get_filled_orders_from_csv(path)
    # group orders by symbol, then build trades for each set of orders that bring quantity to 0
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

            quantity = int(order["quantity"])
            qty_diff = quantity if order["side"] == 'buy' else -quantity

            current_qty += qty_diff
            if current_qty == 0:

                # before : is inclusive, after : is exclusive
                trade_orders = orders[index_of_last_trade:i + 1]
                index_of_last_trade = i + 1

                yield trade_orders

        # NOTE: open trades are not yielded
