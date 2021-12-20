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
            print(
                f"failed to get open intention for {trade['symbol']} on {trade['opened_at'].date()}", type(e), e)
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


def merge_trades(backtest_trades, *trade_lists):

    trades_by_day_lists = list(map(group_trades_by_closed_day, trade_lists))

    days_iso = set()
    for trades_by_day_list in trades_by_day_lists:
        days_iso = days_iso.union(trades_by_day_list.keys())

    for day_iso in sorted(days_iso):

        trades_on_day_list = list(
            map(lambda trades_by_day: trades_by_day.get(day_iso, []), trades_by_day_lists))

        symbols = set()
        for trades_on_day in trades_on_day_list:
            symbols = symbols.union(
                set(map(lambda t: t["symbol"], trades_on_day)))

        for symbol in sorted(symbols):

            symbol_trade_list = []
            for i, trade_list in enumerate(trade_lists):
                trade = next(
                    filter(lambda t: t["symbol"] == symbol, trade_list), None)
                symbol_trade_list.append(trade)
                # if not trade:
                #     print(f"missing trade from set {i} for {day_iso} {symbol}")

            # if len(symbol_trade_list) != len(trade_lists):
            #     continue

            backtest_trade = next(
                filter(lambda t: t["day_after"].isoformat() == day_iso and t["ticker"] == symbol, backtest_trades), None)

            yield {
                "symbol": symbol,
                "backtest_trade": backtest_trade,
                "trades": symbol_trade_list,
            }


def write_performance_csv(environment):
    trades = get_trades(environment)
    path = get_paths()["data"]["outputs"]["performance_csv"].format(
        environment=environment)

    def yield_trades():
        for merged_trade in merge_trades(get_backtest_theoretical_trades(), trades):
            symbol = merged_trade["symbol"]
            backtest_trade = merged_trade["backtest_trade"]
            # since only merging 1 trade set, will always be 1
            trade = merged_trade["trades"][0]

            day_of_loss = backtest_trade["day_of_loss"] if backtest_trade else (
                trade["opened_at"].date())
            day_after = backtest_trade["day_after"] if backtest_trade else (
                trade["closed_at"].date())

            row = {}
            # row = copy(trade["open_intention"])
            # if backtest_trade:
            #     row.update(backtest_trade)
            row["day_of_loss"] = day_of_loss
            row["symbol"] = symbol
            row["day_after"] = day_after
            #
            # entrance slippage
            #
            row["trade_enter_price"] = trade["bought_price"]
            row["trade_enter_intention_price"] = trade["open_intention"]["price"]
            row["backtest_trade_enter_price"] = backtest_trade and backtest_trade["close_day_of_loss"]

            # extra fields
            # TODO: add volume/quantities
            row["backtest_volume_day_of_loss"] = backtest_trade and int(
                backtest_trade["volume_day_of_loss"])

            #
            # exit slippage
            #
            row["trade_exit_price"] = trade["sold_price"]
            row["backtest_trade_exit_price"] = backtest_trade and backtest_trade["open_day_after"]
            # extra fields
            row["backtest_high_day_after"] = backtest_trade and backtest_trade["high_day_after"]
            row["backtest_low_day_after"] = backtest_trade and backtest_trade["low_day_after"]
            row["backtest_close_day_after"] = backtest_trade and backtest_trade["close_day_after"]
            #
            # computed fields
            #
            row["trade_roi"] = (trade["sold_price"] -
                                trade["bought_price"]) / trade["bought_price"]
            row["backtest_trade_roi"] = backtest_trade and backtest_trade["overnight_strategy_roi"]

            # TODO: add slippage %'s enter and exit
            # - correlate close quantity/volume with slippage?
            # - correlate close slippage with price?
            # - correlate close slippage with high-low of day of selling
            yield row

    write_csv(path, yield_trades(), headers=[
        # identifiers
        "day_of_loss",
        "symbol",
        # bonus
        "day_after",
        #
        # entrance slippage
        #
        "trade_enter_price",
        "trade_enter_intention_price",
        "backtest_trade_enter_price",
        # extra fields
        # TODO: add volume/quantities
        "backtest_volume_day_of_loss",
        #
        # exit slippage
        #
        "trade_exit_price",
        "backtest_trade_exit_price",
        # extra fields
        "backtest_high_day_after",
        "backtest_low_day_after",
        "backtest_close_day_after",
        #
        # computed fields
        #
        "trade_roi",
        "backtest_trade_roi",

        # TODO: add slippage %'s enter and exit
        # - correlate close quantity/volume with slippage?
        # - correlate close slippage with price?
        # - correlate close slippage with high-low of day of selling
    ])


if __name__ == "__main__":

    # for environment in ["paper", "prod", "td-cash"]:
    for environment in ["prod"]:
        # print summaries of each
        print(f"{environment} environment:")
        trades = get_trades(environment)
        trades_by_day = group_trades_by_closed_day(trades)
        print_order_summary(trades_by_day)
        print()

        write_performance_csv(environment)

        print("=" * 80)
