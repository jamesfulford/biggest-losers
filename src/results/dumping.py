import os
import typing
from src.outputs import jsonl_dump, json_dump, pathing
from src import types
from src.results import summary, metadata


def rm_f(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass

#
# Orders
#


def overwrite_orders(result_name: str, orders: list[types.FilledOrder]):

    paths = pathing.get_results_folder_paths(result_name)
    path = paths['plain-filled-orders.jsonl']

    rm_f(path)
    jsonl_dump.append_jsonl(path, (o.to_dict() for o in orders))


def read_orders(result_name: str) -> typing.Iterator[types.FilledOrder]:
    paths = pathing.get_results_folder_paths(result_name)
    path = paths['plain-filled-orders.jsonl']
    return (types.FilledOrder.from_dict(o) for o in jsonl_dump.read_jsonl_lines(path))

#
# Intentions
#


def overwrite_intentions(result_name: str, intentions: list[types.Intention]):
    paths = pathing.get_results_folder_paths(result_name)
    path = paths['intentions.jsonl']

    rm_f(path)
    jsonl_dump.append_jsonl(path, (i.to_dict() for i in intentions))


def append_intentions(result_name: str, intentions: list[types.Intention]):
    paths = pathing.get_results_folder_paths(result_name)
    path = paths['intentions.jsonl']

    jsonl_dump.append_jsonl(path, (i.to_dict() for i in intentions))


def read_intentions(result_name: str) -> typing.Iterator[types.Intention]:
    paths = pathing.get_results_folder_paths(result_name)
    path = paths['intentions.jsonl']
    return (types.Intention.from_dict(i) for i in jsonl_dump.read_jsonl_lines(path))

#
# Intention Filled Orders
#


def overwrite_intention_filled_orders(result_name: str, orders: list[types.FilledOrder]):
    paths = pathing.get_results_folder_paths(result_name)
    path = paths['intentioned-filled-orders.jsonl']

    rm_f(path)
    jsonl_dump.append_jsonl(path, (o.to_dict() for o in orders))


def read_intention_filled_orders(result_name: str) -> typing.Iterator[types.FilledOrder]:
    paths = pathing.get_results_folder_paths(result_name)
    path = paths['intentioned-filled-orders.jsonl']
    return (types.FilledOrder.from_dict(o) for o in jsonl_dump.read_jsonl_lines(path))

#
# Summary
#


def overwrite_summary(result_name: str, summary: summary.Summary):
    paths = pathing.get_results_folder_paths(result_name)
    path = paths['summary.json']

    rm_f(path)

    json_dump.write_json(path, summary.to_dict())


def read_summary(result_name: str) -> summary.Summary:
    paths = pathing.get_results_folder_paths(result_name)
    path = paths['summary.json']
    return summary.Summary.from_dict(json_dump.read_json(path))

#
# Metadata
#


def overwrite_metadata(result_name: str, metadata: metadata.Metadata):
    paths = pathing.get_results_folder_paths(result_name)
    path = paths['metadata.json']

    rm_f(path)

    json_dump.write_json(path, metadata.to_dict())


def read_metadata(result_name: str) -> metadata.Metadata:
    paths = pathing.get_results_folder_paths(result_name)
    path = paths['metadata.json']
    return metadata.Metadata.from_dict(json_dump.read_json(path))
