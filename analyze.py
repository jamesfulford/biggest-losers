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
        get_paths()['data']["outputs"]["biggest_losers_csv"], date.today() - timedelta(days=10))


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


if __name__ == "__main__":

    paper_trades_by_day = group_trades_by_closed_day(get_trades("paper"))
    prod_trades_by_day = group_trades_by_closed_day(get_trades("prod"))

    print(f"paper environment:")
    print_order_summary(paper_trades_by_day)
    print()

    print("=" * 80)

    print(f"prod environment:")
    print_order_summary(prod_trades_by_day)
    print()

    last_day_trading_iso = sorted(
        prod_trades_by_day.keys())[0]

    print("=" * 80)

    last_day_trades_paper = paper_trades_by_day[last_day_trading_iso]
    last_day_trades_prod = prod_trades_by_day[last_day_trading_iso]

    backtest_trades = get_backtest_theoretical_trades()

    symbols = set(map(lambda t: t["symbol"], last_day_trades_paper)).union(
        set(map(lambda t: t["symbol"], last_day_trades_prod)))

    print("t".rjust(6), 'paper'.rjust(6), 'prod'.rjust(6), 'back'.rjust(6))
    for symbol in sorted(symbols):
        # for each paper/prod trade, do inner join with paper,prod,backtest trades and print when there are misses
        paper_trade = next(
            filter(lambda t: t["symbol"] == symbol, last_day_trades_paper), None)
        if not paper_trade:
            print(f"missing paper trade for {symbol}")
            continue

        prod_trade = next(
            filter(lambda t: t["symbol"] == symbol, last_day_trades_prod), None)
        if not prod_trade:
            print(f"missing prod trade for {symbol}")
            continue

        backtest_trade = next(
            filter(lambda t: t["day_after"].isoformat() == last_day_trading_iso and t["ticker"] == symbol, backtest_trades), None)
        if not backtest_trade:
            print(f"missing backtest trade for {symbol}")
            continue

        paper_price = paper_trade["bought_price"]
        prod_price = prod_trade["bought_price"]
        backtest_price = backtest_trade["close_day_of_loss"]

        print(symbol.rjust(6), (str(round(paper_price, 1))).rjust(6),
              (str(round(prod_price, 2))).rjust(6), (str(round(backtest_price, 1))).rjust(6))
