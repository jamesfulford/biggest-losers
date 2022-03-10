from collections.abc import MutableMapping
import logging
from typing import Any, Mapping, Optional, cast
import argparse


from src.csv_dump import write_csv
from src.intention import get_intentions_by_algo
from src.pathing import get_paths
from src.reporting.trades import Trade, get_closed_trades_from_orders_csv


class TradeWithOpenIntention(Trade):
    open_intention: Optional[dict[str, Any]]


def get_trades(environment_name: str, algo_name: str) -> list[TradeWithOpenIntention]:
    path = get_paths(environment_name)["data"]["outputs"]["filled_orders_csv"]
    trades = list(get_closed_trades_from_orders_csv(path))
    trades = cast(list[TradeWithOpenIntention], trades)

    opening_day_intentions = get_intentions_by_algo(
        environment_name, algo_name
    )

    # enrich trade with intentions recorded at time of trade opening
    for trade in trades:
        open_intention: Optional[dict[str, Any]] = next(
            filter(
                lambda intention: intention["symbol"] == trade["symbol"] and intention["datetime"].strftime(
                    "%Y-%m-%d %H:%M") == trade["opened_at"].strftime("%Y-%m-%d %H:%M"),
                opening_day_intentions,
            ), None
        )
        trade["open_intention"] = open_intention

    return trades


def group_trades_by_closed_day(trades: list[Trade]) -> Mapping[str, list[Trade]]:
    # by day
    trades_by_closed_day = {}

    for trade in trades:
        key = trade["closed_at"].date().isoformat()
        trades_by_closed_day[key] = trades_by_closed_day.get(key, []) + [trade]

    return trades_by_closed_day


# https://www.freecodecamp.org/news/how-to-flatten-a-dictionary-in-python-in-4-different-ways/


def _flatten_dict_gen(d, parent_key, sep):
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            yield from flatten_dict(v, new_key, sep=sep).items()
        else:
            yield new_key, v


def flatten_dict(d: MutableMapping, parent_key: str = '', sep: str = '.'):
    return dict(_flatten_dict_gen(d, parent_key, sep))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--algoname", type=str, required=True)
    parser.add_argument("--environments", type=str, required=True)

    args = parser.parse_args()

    environments: list[str] = args.environments.split(",")

    algo_name: str = args.algoname
    logging.info(f"Algorithm name: {algo_name}")
    logging.info(f"Environments: {args.environments}")
    for environment in environments:
        logging.info(f"Reading {environment}...")
        trades = sorted(get_trades(environment, algo_name),
                        key=lambda t: t["opened_at"])

        logging.info(
            f"{environment} had {len(trades)} trades. Writing to csv...")

        def prepare_row(trade: dict) -> dict:
            row = flatten_dict(trade)
            return row

        path = get_paths(environment)['data']["outputs"]["performance_csv"].format(
            environment=environment)
        write_csv(path, (prepare_row(cast(dict, trade)) for trade in trades), headers=[
            'opened_at', 'symbol', 'closed_at', 'bought_price', 'sold_price', 'price_difference', 'quantity', 'bought_cost', 'sold_cost',  'profit_loss', 'roi', 'is_win'])
