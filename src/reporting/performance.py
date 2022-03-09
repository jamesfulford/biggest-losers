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


def get_backtest_theoretical_trades():
    # TODO: this will not have most recent data unless we rebuild cache
    # TODO: this only does biggest losers, we should evaluate more generically
    return get_lines_from_biggest_losers_csv(
        get_paths()["data"]["outputs"]["biggest_losers_csv"]
    )


def merge_trades(backtest_trades, trades):
    trades_by_day = group_trades_by_closed_day(trades)

    days_iso = set(trades_by_day.keys())

    for day_iso in sorted(days_iso):
        trades_on_day = trades_by_day.get(day_iso, [])

        symbols = set(map(lambda t: t["symbol"], trades_on_day))

        for symbol in sorted(symbols):
            trade = next(
                filter(
                    lambda t: t["symbol"] == symbol
                    and t["closed_at"].date().isoformat() == day_iso,
                    trades,
                ),
                None,
            )

            backtest_trade = next(
                filter(
                    lambda t: t["day_after"].isoformat() == day_iso
                    and t["ticker"] == symbol,
                    backtest_trades,
                ),
                None,
            )

            yield {
                "symbol": symbol,
                "backtest_trade": backtest_trade,
                "trade": trade,
            }


def write_performance_csv(environment):
    trades = get_trades(environment)
    path = get_paths()["data"]["outputs"]["performance_csv"].format(
        environment=environment
    )

    def yield_trades():
        # TODO: include the biggest losers we would have bought in backtest so we can see difference
        # TODO: fill in some backtest values when values from csv are missing (less nulls!)
        for merged_trade in merge_trades(get_backtest_theoretical_trades(), trades):
            backtest_trade = merged_trade["backtest_trade"]
            trade = merged_trade["trade"]

            row = {}

            for key in trade.keys() - {"open_intention"}:
                row[f"t_{key}"] = trade[key]
            row["t_roi"] = (trade["sold_price"] - trade["bought_price"]) / trade[
                "bought_price"
            ]

            if "open_intention" in trade:
                for key in trade["open_intention"].keys() - {"symbol"}:
                    row[f"oi_{key}"] = trade["open_intention"][key]
                row["entry_slippage"] = (row["t_bought_price"] - row["oi_price"]) / row[
                    "oi_price"
                ]

            if backtest_trade:
                for key in backtest_trade.keys() - {"ticker"}:
                    row[f"b_{key}"] = backtest_trade[key]
                row["b_overnight_strategy_is_win"] = bool(
                    row["b_overnight_strategy_is_win"]
                )
                row["entry_disparity"] = (
                    row["t_bought_price"] - row["b_close_day_of_action"]
                ) / row["b_close_day_of_action"]
                row["close_disparity"] = (
                    row["b_open_day_after"] - row["t_sold_price"]
                ) / row["b_open_day_after"]

                row["total_waste"] = row["b_overnight_strategy_roi"] - row["t_roi"]

            yield row

    write_csv(
        path,
        yield_trades(),
        headers=[
            # identifiers
            "b_day_of_action",
            "t_symbol",
            "b_day_after",
            # results
            "t_roi",
            "t_is_win",
            "b_overnight_strategy_roi",
            "b_overnight_strategy_is_win",
            "entry_slippage",
            "entry_disparity",
            "close_disparity",
            "total_waste",
            # useful fields
            "oi_price",
            "t_bought_price",
            "t_sold_price",
            "b_close_day_of_action",
            "b_open_day_after",
            "t_quantity",
            "oi_quantity",
            "b_volume_day_of_action",
        ],
    )


def main():
    for trade in sorted(get_trades('paper'), key=lambda t: t["opened_at"]):
        print(f"{trade['symbol']},{trade['opened_at'].date().isoformat()},{trade['opened_at'].strftime('%H:%M')},{trade['closed_at'].strftime('%H:%M')},{trade['bought_price']},{trade['sold_price']},{trade['quantity']},{trade['roi']:.1%}")

# if __name__ == "__main__":

    # for environment in ["paper", "prod", "td-cash", "cash1", "intrac1"]:
    #     logging.info(f"Dumping performance csv for {environment}...")
    #     print()
    #     write_performance_csv(environment)
    #     print()
