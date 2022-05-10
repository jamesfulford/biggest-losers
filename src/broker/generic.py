import datetime
import functools
import logging
import os
import typing
from src.broker.types import Account, FilledOrder, Order, Position

from src.data.td.td import get_quote


@functools.lru_cache(maxsize=1)
def get_broker_module(broker_name: typing.Optional[str] = None) -> typing.Any:
    if not broker_name:
        broker_name = os.environ.get('BROKER')

    if broker_name == 'alpaca':
        import src.broker.alpaca as alpaca
        return alpaca
    elif broker_name == 'td':
        import src.broker.td as td
        return td
    elif broker_name == "pizzalabs":
        import src.broker.pizzalabs as pizzalabs
        return pizzalabs
    else:
        raise Exception(f'Unknown broker: {broker_name}')


def buy_symbol_at_close(symbol: str, qty: float) -> None:
    return get_broker_module().buy_symbol_at_close(symbol, qty)


def sell_symbol_at_open(symbol: str, qty: float) -> None:
    return get_broker_module().sell_symbol_at_open(symbol, qty)


def buy_symbol_market(symbol: str, qty: float) -> None:
    return get_broker_module().buy_symbol_market(symbol, qty)


def sell_symbol_market(symbol: str, qty: float) -> None:
    return get_broker_module().sell_symbol_market(symbol, qty)


def buy_limit(symbol: str, qty: float, limit_price: float, allow_premarket: bool = False, gtc: bool = False) -> None:
    return get_broker_module().buy_limit(symbol, qty, limit_price, allow_premarket=allow_premarket, gtc=gtc)


def sell_limit(symbol: str, qty: float, limit_price: float, allow_premarket: bool = False, gtc: bool = False) -> None:
    return get_broker_module().sell_limit(symbol, qty, limit_price, allow_premarket=allow_premarket, gtc=gtc)


def buy_limit_thru(symbol: str, quantity: int, buffer: float = .05, **limit_args):
    quote = get_quote(symbol)
    price = quote['ask'] + buffer
    logging.debug(
        f"Buying {quantity} shares of {symbol} at {price} ({quote['ask']} + {buffer})")
    buy_limit(symbol, quantity, price, **limit_args)


def sell_limit_thru(symbol: str, quantity: int, buffer: float = .05, **limit_args):
    quote = get_quote(symbol)
    price = quote['bid'] - buffer
    logging.debug(
        f"Buying {quantity} shares of {symbol} at {price} ({quote['bid']} - {buffer})")
    sell_limit(symbol, quantity, price, **limit_args)


def place_oco(
        symbol: str,
        quantity: float,
        take_profit_limit: float,
        stop_loss_stop: float,
        stop_loss_limit: typing.Optional[float] = None) -> None:
    return get_broker_module().place_oco(symbol, quantity, take_profit_limit, stop_loss_stop, stop_loss_limit=stop_loss_limit)


def get_account() -> Account:
    return get_broker_module().get_account()


def get_positions() -> list[Position]:
    return get_broker_module().get_positions()


def get_filled_orders(start: datetime.date, end: datetime.date) -> list[FilledOrder]:
    return get_broker_module().get_filled_orders(start, end)


def get_open_orders() -> list[Order]:
    return get_broker_module().get_open_orders()


def cancel_all_orders():
    get_broker_module().cancel_all_orders()


def main():
    import src.broker.alpaca as alpaca
    import src.broker.td as td
    import json

    import logging
    logging.getLogger().setLevel(logging.DEBUG)

    print(json.dumps(td.get_positions(), indent=2, sort_keys=True))
    print(json.dumps(alpaca.get_positions(), indent=2, sort_keys=True))
    print()
