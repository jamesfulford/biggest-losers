import typing
from src.results import dumping, metadata
from src import types


def get_orders(result_name: str) -> typing.Iterable[types.FilledOrder]:
    orders = list(dumping.read_intention_filled_orders(result_name))
    return orders


def get_trades(result_name: str) -> typing.Iterable[types.Trade]:
    orders = list(dumping.read_intention_filled_orders(result_name))
    trades = list(types.Trade.from_orders(orders))
    return trades


def get_metadata(result_name: str) -> metadata.Metadata:
    return dumping.read_metadata(result_name)
