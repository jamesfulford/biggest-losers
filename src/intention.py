from datetime import date, datetime
import logging
from zoneinfo import ZoneInfo
from copy import copy
from functools import lru_cache

from src.broker.dry_run import DRY_RUN
from src.csv_dump import write_csv
from src.jsonl_dump import append_jsonl
from src.pathing import get_paths


MARKET_TZ = ZoneInfo("America/New_York")


def get_order_intentions_csv_path(algo_name: str, environment_name=None):
    return get_paths(target_environment_name=environment_name)['data']['outputs']['order_intentions_csv'].format(algo_name=algo_name)


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
        path = get_order_intentions_csv_path(algo_name)

    metadata.update({"algo_name": algo_name})

    append_jsonl(path, [convert_intention_to_format(
        intention, metadata) for intention in intentions])


def record_intentions(today: date, order_intentions: list, metadata: dict = {}):
    # TODO: remove this, replace with log_intentions in losers script
    # TODO: to remove this, gotta update reporting scripts
    path = None
    if DRY_RUN:
        logging.warning(
            "DRY_RUN: not writing order intentions (may overwrite), instead writing to stdout")
    else:
        path = get_order_intentions_csv_path(today.isoformat())

    def yield_lines(lines):
        for line in lines:
            yield convert_intention_to_format(line, metadata)

    write_csv(path, yield_lines(order_intentions), headers=[
              "Date", "Time", "Symbol", "Quantity", "Price", "Side"])


@lru_cache(maxsize=1)
def get_intentions_by_day(environment_name: str, day: date):
    path = get_order_intentions_csv_path(
        day, environment_name=environment_name)

    lines = []
    with open(path, "r") as f:
        lines.extend(f.readlines())

    headers = lines[0].strip().split(",")

    # remove newlines and header row
    lines = [l.strip() for l in lines[1:]]

    # convert to dicts
    raw_dict_lines = [dict(zip(headers, l.strip().split(","))) for l in lines]

    lines = []
    for l in raw_dict_lines:
        # (pass all extra columns through, only touch these specific ones)
        row = l
        row.update({
            "datetime": datetime.strptime(l["Date"] + " " + l["Time"], '%Y-%m-%d %H:%M:%S').astimezone(MARKET_TZ),
            "symbol": l["Symbol"],
            "quantity": float(l["Quantity"]),
            "price": float(l["Price"]),
            "side": l["Side"].lower(),
        })
        del row["Date"]
        del row["Time"]
        del row["Symbol"]
        del row["Quantity"]
        del row["Price"]
        del row["Side"]

        lines.append(row)

    return lines
