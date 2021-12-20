from datetime import date, datetime
from zoneinfo import ZoneInfo
from copy import copy

from backtest import get_lines_from_biggest_losers_csv
from src.csv_dump import write_csv
from src.intention import get_intentions_by_day
from src.pathing import get_paths
from src.trades import get_closed_trades_from_orders_csv


MARKET_TZ = ZoneInfo("America/New_York")


def get_trades(environment_name):
    path = get_paths(environment_name)['data']["outputs"]["filled_orders_csv"]
    trades = list(get_closed_trades_from_orders_csv(path))

    # enrich trade with intentions recorded at time of trade opening
    for trade in trades:

        try:
            opening_day_intentions = get_intentions_by_day(
                environment_name, trade["opened_at"].date())
            open_intention = next(filter(
                lambda intention: intention["symbol"] == trade["symbol"], opening_day_intentions))
            trade["open_intention"] = open_intention
        except FileNotFoundError:
            pass
        except Exception as e:
            pass
            # print(
            #     f"failed to get open intention for {trade['symbol']} on {trade['opened_at'].date()}", type(e), e)
            # raise e
    return trades


def group_trades_by_closed_day(trades):
    # by day
    trades_by_closed_day = {}

    for trade in trades:
        key = trade["closed_at"].date().isoformat()
        trades_by_closed_day[key] = trades_by_closed_day.get(key, []) + [trade]

    return trades_by_closed_day


def get_backtest_theoretical_trades():
    return get_lines_from_biggest_losers_csv(
        get_paths()['data']["outputs"]["biggest_losers_csv"], date(2020, 1, 1))


def print_order_summary(trades_by_closed_day):
    total_change = 0
    rois = []
    today = datetime.now().date()
    for day, trades_on_day in sorted(trades_by_closed_day.items()):
        change = 0
        used_cash = 0
        for trade in trades_on_day:
            change += trade["profit_loss"]
            used_cash += trade["bought_cost"]

        roi = change / used_cash
        print(f"{day}: {round(change, 2)} ({round(100 * roi, 1)}%)")

        total_change += change
        rois.append(roi)

        if today == trades_on_day[0]["closed_at"].date():
            print()
            print(f"Today's trading results:")
            for trade in sorted(trades_on_day, key=lambda t: t["profit_loss"]):
                profit_loss = round(trade["profit_loss"], 2)
                profit_loss_str = str(profit_loss)
                decimal_places = len(profit_loss_str.split(".")[-1])
                profit_loss_str = profit_loss_str + "0" * (2 - decimal_places)

                print(trade["symbol"].rjust(8),
                      profit_loss_str.rjust(10), str(round(100 * trade["roi"], 1)).rjust(6) + "%")

    print()

    geo_roi = g_avg(list(map(lambda roi: 1 + roi, rois))) - 1
    print(f"Total: {round(total_change, 2)}")
    print(f"  days: {len(trades_by_closed_day)}")
    print(f"  daily average: {round(100 * geo_roi, 1)}%")
    annualized_roi = ((1 + geo_roi) ** 250) - 1
    print(
        f"  annual roi: {round(100 * annualized_roi, 1)}% ({round(annualized_roi + 1, 1)}x)")


def g_avg(l):
    assert not any(map(lambda x: x <= 0, l)), "All elements must be positive"
    m = 1
    for i in l:
        m *= i
    return m ** (1/len(l))


def merge_trades(backtest_trades, trades):
    trades_by_day = group_trades_by_closed_day(trades)

    days_iso = set(trades_by_day.keys())

    for day_iso in sorted(days_iso):
        trades_on_day = trades_by_day.get(day_iso, [])

        symbols = set(map(lambda t: t["symbol"], trades_on_day))

        for symbol in sorted(symbols):
            trade = next(
                filter(lambda t: t["symbol"] == symbol and t["closed_at"].date().isoformat() == day_iso, trades), None)
            # if not trade:
            #     print(f"missing trade for {day_iso} {symbol}")

            backtest_trade = next(
                filter(lambda t: t["day_after"].isoformat() == day_iso and t["ticker"] == symbol, backtest_trades), None)

            yield {
                "symbol": symbol,
                "backtest_trade": backtest_trade,
                "trade": trade,
            }


def write_performance_csv(environment):
    trades = get_trades(environment)
    path = get_paths()["data"]["outputs"]["performance_csv"].format(
        environment=environment)

    def yield_trades():
        for merged_trade in merge_trades(get_backtest_theoretical_trades(), trades):
            backtest_trade = merged_trade["backtest_trade"]
            trade = merged_trade["trade"]

            row = {}

            for key in trade.keys() - {"open_intention"}:
                row[f"t_{key}"] = trade[key]

            if "open_intention" in trade:
                for key in trade["open_intention"].keys() - {"symbol"}:
                    row[f"oi_{key}"] = trade["open_intention"][key]

            if backtest_trade:
                for key in backtest_trade.keys() - {"ticker"}:
                    row[f"b_{key}"] = backtest_trade[key]
                row["b_overnight_strategy_is_win"] = bool(
                    row["b_overnight_strategy_is_win"])

            #
            # computed fields
            #
            row["t_roi"] = (trade["sold_price"] -
                            trade["bought_price"]) / trade["bought_price"]

            # TODO: add slippage %'s enter and exit
            # - correlate close quantity/volume with slippage?
            # - correlate close slippage with price?
            # - correlate close slippage with high-low of day of selling
            yield row

    write_csv(path, yield_trades(), headers=[
        # opening
        "t_opened_at",
        "b_day_of_loss",
        "oi_datetime",
        # ticker
        "t_symbol",
        # closing
        "b_day_after",
        "t_closed_at",

        # timing extra fields
        "b_day_of_loss_month",
        "b_day_of_loss_weekday",
        "b_days_overnight",
        "b_overnight_has_holiday_bool",

        # entrance
        "/",
        "t_bought_price",
        "t_quantity",

        "oi_price",
        "oi_quantity",

        "b_close_day_of_loss",
        "b_volume_day_of_loss",

        # exit
        "/",
        "t_sold_price",
        "b_open_day_after",

        # results
        "/",
        "t_price_difference",
        "t_profit_loss",
        "t_roi",
        "t_is_win",

        "b_overnight_strategy_roi",
        "b_overnight_strategy_is_win",

        # computed fields
        # TODO: add slippage %'s enter and exit
        # - correlate close quantity/volume with slippage?
        # - correlate close slippage with price?
        # - correlate close slippage with high-low of day of selling
        "|",
    ])


if __name__ == "__main__":

    for environment in ["paper", "prod", "td-cash"]:
        # print summaries of each
        print(f"{environment} environment:")
        trades = get_trades(environment)
        trades_by_day = group_trades_by_closed_day(trades)
        print_order_summary(trades_by_day)
        print()

        write_performance_csv(environment)

        print("=" * 80)
