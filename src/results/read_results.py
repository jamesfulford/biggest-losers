import typing
import src.results.dumping as dumping
import src.types as types


def get_orders(result_name: str) -> typing.Iterable[types.FilledOrder]:
    orders = list(dumping.read_intention_filled_orders(result_name))
    return orders


def get_trades(result_name: str) -> typing.Iterable[types.Trade]:
    orders = list(dumping.read_intention_filled_orders(result_name))
    trades = list(types.Trade.from_orders(orders))
    return trades
