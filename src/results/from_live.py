import re
import src.types as types
import src.results.dumping as dumping


def update_filled_orders(result_name: str, orders: types.FilledOrder):
    # TODO: implement
    # someone needs to get orders from broker
    #  - not here, so we can filter by algo or something
    # add in intentions, then write to intention-filled-orders
    # clear other files so not left stale, but keep intentions
    pass


def record_intentions(result_name: str, intentions: list[types.Intention]):
    dumping.append_intentions(result_name, intentions)
