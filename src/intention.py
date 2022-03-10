from datetime import datetime
import logging
from typing import Any
from zoneinfo import ZoneInfo
from copy import copy
from functools import lru_cache
import json

from src.broker.dry_run import DRY_RUN
from src.jsonl_dump import append_jsonl
from src.pathing import get_paths


MARKET_TZ = ZoneInfo("America/New_York")


def get_order_intentions_jsonl_path(algo_name: str, environment_name=None):
    return get_paths(target_environment_name=environment_name)['data']['outputs']['order_intentions_jsonl'].format(algo_name=algo_name)


def convert_intention_to_format(intention: dict, metadata: dict = {}):
    now = intention['datetime'].astimezone(MARKET_TZ)
    ticker = intention['symbol']
    quantity = intention['quantity']
    price = intention['price']
    side = intention['side']

    row = copy(intention)
    del row["datetime"]
    del row["symbol"]
    del row["quantity"]
    del row["price"]
    del row["side"]

    row["Date"] = now.strftime('%Y-%m-%d')
    row["Time"] = now.strftime('%H:%M:%S')
    row["Symbol"] = ticker
    row["Quantity"] = quantity
    row["Price"] = price
    row["Side"] = side.upper()

    row.update(metadata)
    return row


def log_intentions(algo_name: str, intentions: list[dict], metadata: dict = {}):
    path = None
    if DRY_RUN:
        logging.warning(
            "DRY_RUN: not writing order intentions (may overwrite), instead writing to stdout")
    else:
        path = get_order_intentions_jsonl_path(algo_name)

    metadata.update({"algo_name": algo_name})

    append_jsonl(path, [convert_intention_to_format(
        intention, metadata) for intention in intentions])


@lru_cache(maxsize=1)
def get_intentions_by_algo(environment_name: str, algo_name: str) -> list[dict[str, Any]]:
    path = get_order_intentions_jsonl_path(
        algo_name, environment_name=environment_name)

    lines = []
    with open(path, "r") as f:
        lines.extend(f.readlines())

    lines = [json.loads(l) for l in lines]

    lines = [revert_intention_format(l) for l in lines]
    return lines


def revert_intention_format(row: dict):
    # (pass all extra columns through, only touch these specific ones)
    row.update({
        "datetime": datetime.strptime(row["Date"] + " " + row["Time"], '%Y-%m-%d %H:%M:%S').astimezone(MARKET_TZ),
        "symbol": row["Symbol"],
        "quantity": float(row["Quantity"]),
        "price": float(row["Price"]),
        "side": row["Side"].lower(),
    })
    del row["Date"]
    del row["Time"]
    del row["Symbol"]
    del row["Quantity"]
    del row["Price"]
    del row["Side"]

    return row
