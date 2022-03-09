from collections.abc import MutableMapping
import logging
from zoneinfo import ZoneInfo
import argparse


from src.csv_dump import write_csv
from src.intention import get_intentions_by_algo
from src.pathing import get_paths
from src.reporting.trades import get_closed_trades_from_orders_csv


def get_trades(environment_name: str, algo_name: str):
    path = get_paths(environment_name)["data"]["outputs"]["filled_orders_csv"]
    trades = list(get_closed_trades_from_orders_csv(path))

    # enrich trade with intentions recorded at time of trade opening
    for trade in trades:
        try:
            opening_day_intentions = get_intentions_by_algo(
                environment_name, algo_name
            )
            open_intention = next(
                filter(
                    lambda intention: intention["symbol"] == trade["symbol"] and intention["datetime"].strftime(
                        "%Y-%m-%d %H:%M") == trade["opened_at"].strftime("%Y-%m-%d %H:%M"),
                    opening_day_intentions,
                ), None
            )
            trade["open_intention"] = open_intention
        except FileNotFoundError:
            pass
        except Exception as e:
            logging.exception(
                f"Unexpected failure to get open intention for {trade['symbol']} on {trade['opened_at'].date()}")
    return trades


def group_trades_by_closed_day(trades):
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
    #
    # TODO: write csvs, given environments in sys.argv

    parser = argparse.ArgumentParser()
    parser.add_argument("--algoname", type=str, required=True)
    parser.add_argument("--environments", type=str, required=True)

    args = parser.parse_args()

    args.environments = args.environments.split(",")

    algo_name = args.algoname
    # logging.info(f"Algorithm name: {algo_name}")
    # logging.info(f"Environments: {args.environments}")
    for environment in args.environments:
        # logging.info(f"Reading {environment}...")
        trades = sorted(get_trades(environment, algo_name),
                        key=lambda t: t["opened_at"])

        # logging.info(
        #    f"{environment} had {len(trades)} trades. Writing to csv...")

        def prepare_row(trade: dict) -> dict:
            row = flatten_dict(trade)
            return row

        path = get_paths(environment)['data']["outputs"]["performance_csv"].format(
            environment=environment)
        write_csv(path, (prepare_row(trade) for trade in trades), headers=[
            'opened_at', 'symbol', 'closed_at', 'bought_price', 'sold_price', 'price_difference', 'quantity', 'bought_cost', 'sold_cost',  'profit_loss', 'roi', 'is_win'])
