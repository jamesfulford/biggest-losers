import logging
from zoneinfo import ZoneInfo

from src.strat.losers.gridsearch_backtest_losers import get_lines_from_biggest_losers_csv
from src.csv_dump import write_csv
from src.intention import get_intentions_by_day
from src.pathing import get_paths
from src.reporting.trades import get_closed_trades_from_orders_csv


MARKET_TZ = ZoneInfo("America/New_York")


def get_trades(environment_name):
    path = get_paths(environment_name)["data"]["outputs"]["filled_orders_csv"]
    trades = list(get_closed_trades_from_orders_csv(path))

    # enrich trade with intentions recorded at time of trade opening
    for trade in trades:
        try:
            # TODO: add intentions from JSONL for a given algorithm
            opening_day_intentions = get_intentions_by_day(
                environment_name, trade["opened_at"].date()
            )
            open_intention = next(
                filter(
                    lambda intention: intention["symbol"] == trade["symbol"],
                    opening_day_intentions,
                )
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


def main():
    # TODO: write csvs, given environments in sys.argv
    for trade in sorted(get_trades('paper'), key=lambda t: t["opened_at"]):
        print(f"{trade['symbol']},{trade['opened_at'].date().isoformat()},{trade['opened_at'].strftime('%H:%M')},{trade['closed_at'].strftime('%H:%M')},{trade['bought_price']},{trade['sold_price']},{trade['quantity']},{trade['roi']:.1%}")
