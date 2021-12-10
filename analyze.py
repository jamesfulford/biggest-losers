from datetime import date, datetime, timedelta
from backtest import get_lines_from_biggest_losers_csv
from src.pathing import get_paths
from src.trades import get_closed_trades_from_orders_csv


def get_trades(environment_name):
    path = get_paths(environment_name)['data']["outputs"]["filled_orders_csv"]
    trades = list(get_closed_trades_from_orders_csv(path))
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


def merge_trades(paper_trades, prod_trades, backtest_trades):
    paper_trades_by_day = group_trades_by_closed_day(paper_trades)
    prod_trades_by_day = group_trades_by_closed_day(prod_trades)

    days_iso = set(paper_trades_by_day.keys()).intersection(
        set(prod_trades_by_day.keys()))

    for day_iso in sorted(days_iso):
        trades_paper = paper_trades_by_day[day_iso]
        trades_prod = prod_trades_by_day[day_iso]

        symbols = set(map(lambda t: t["symbol"], trades_paper)).union(
            set(map(lambda t: t["symbol"], trades_prod)))

        for symbol in sorted(symbols):
            # for each paper/prod trade, do inner join with paper,prod,backtest trades and print when there are misses
            paper_trade = next(
                filter(lambda t: t["symbol"] == symbol, trades_paper), None)
            if not paper_trade:
                print(f"missing paper trade for {day_iso} {symbol}")
                continue

            prod_trade = next(
                filter(lambda t: t["symbol"] == symbol, trades_prod), None)
            if not prod_trade:
                print(f"missing prod trade for {day_iso} {symbol}")
                continue

            backtest_trade = next(
                filter(lambda t: t["day_after"].isoformat() == day_iso and t["ticker"] == symbol, backtest_trades), None)
            if not backtest_trade:
                print(f"missing backtest trade for {day_iso} {symbol}")
                continue

            yield {
                "symbol": symbol,
                "paper_trade": paper_trade,
                "prod_trade": prod_trade,
                "backtest_trade": backtest_trade
            }


if __name__ == "__main__":
    paper_trades = get_trades("paper")
    prod_trades = get_trades("prod")

    # print summaries of each
    print(f"paper environment:")
    paper_trades_by_day = group_trades_by_closed_day(paper_trades)
    print_order_summary(paper_trades_by_day)
    print()

    print("=" * 80)

    print(f"prod environment:")
    prod_trades_by_day = group_trades_by_closed_day(prod_trades)
    print_order_summary(prod_trades_by_day)
    print()

    print("=" * 80)

    #
    # merge trades
    #

    with open(get_paths()["data"]["outputs"]["performance_csv"], 'w') as f:
        headers = [
            # identifiers
            "day_of_loss",
            "symbol",
            # bonus
            "day_after",
            #
            # entrance slippage
            #
            "paper_trade_enter_price",
            "prod_trade_enter_price",
            "backtest_trade_enter_price",
            # extra fields
            # TODO: add volume/quantities
            "backtest_volume_day_of_loss",
            #
            # exit slippage
            #
            "paper_trade_exit_price",
            "prod_trade_exit_price",
            "backtest_trade_exit_price",
            # extra fields
            "backtest_high_day_after",
            "backtest_low_day_after",
            "backtest_close_day_after",
            #
            # computed fields
            #

            # Initial results seem to show that prod trade enters at the same price as the backtest says.

            # TODO: add slippage %'s enter and exit
            # - correlate close quantity/volume with slippage?
            # - correlate close slippage with price?
            # - correlate close slippage with high-low of day of selling

            # TODO: add rois, add best possible roi
        ]
        f.write(",".join(headers) + "\n")

        # TODO: merge in paper and prod trade intentions
        for merged_trade in merge_trades(paper_trades, prod_trades, get_backtest_theoretical_trades()):
            f.write(",".join([
                merged_trade["backtest_trade"]["day_of_loss"].isoformat(),
                merged_trade["backtest_trade"]["ticker"],
                merged_trade["backtest_trade"]["day_after"].isoformat(),

                str(round(merged_trade["paper_trade"]["bought_price"], 4)),
                str(round(merged_trade["prod_trade"]["bought_price"], 4)),
                str(round(merged_trade["backtest_trade"]
                    ["close_day_of_loss"], 4)),

                str(round(merged_trade["backtest_trade"]
                    ["volume_day_of_loss"], 0)),

                str(round(merged_trade["paper_trade"]["sold_price"], 4)),
                str(round(merged_trade["prod_trade"]["sold_price"], 4)),
                str(round(merged_trade["backtest_trade"]
                    ["open_day_after"], 4)),

                str(round(merged_trade["backtest_trade"]
                    ["high_day_after"], 4)),
                str(round(merged_trade["backtest_trade"]["low_day_after"], 4)),
                str(round(merged_trade["backtest_trade"]
                    ["close_day_after"], 4)),
            ]) + "\n")
