from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.broker.dry_run import DRY_RUN
from src.broker.alpaca import buy_symbol_at_close, get_account, get_positions, sell_symbol_at_open
from src.losers import get_biggest_losers
from src.criteria import is_skipped_day, is_warrant


MARKET_TZ = ZoneInfo("America/New_York")


def print_losers_csv(losers):
    # omitting n,t,vw
    cols = ["T", "rank", "percent_change", "c", "v", "h", "l", "o"]
    print(",".join(cols))
    for loser in losers:
        s = ""
        for col in cols:
            s += "{},".format(loser[col])
        print(s)

    print()


def print_current_positions():
    positions = get_positions()
    print('DEBUG: current positions', positions)


def buy_biggest_losers_at_close(today):
    minimum_loss_percent = 0.1  # down at least 10%; aka percent_change < -0.1

    closing_price_min = 0.0  # no price requirement
    minimum_volume = 0  # no volume requirement, let's see how we do.
    def warrant_criteria(c): return not is_warrant(c["T"])

    top_n = 10

    use_geometric = True

    # geometric
    # to simulate cash settling, do .33. That's using 1/3 of cash every night.
    # 1.0 is using all cash every night.
    # higher will start using margin. Overnight margin has special rules, max is probably near 1.5 as far as I can tell
    cash_percent_to_use = 1.0

    # arithmetic
    base_nominal = 10000

    #
    # Filter losers
    #

    losers = get_biggest_losers(today, bust_cache=True, top_n=1000) or []
    losers = list(
        filter(lambda l: l["percent_change"] < -minimum_loss_percent, losers))

    print_losers_csv(losers)

    losers = list(filter(lambda l: l["c"] > closing_price_min, losers))
    losers = list(filter(lambda l: l["v"] > minimum_volume, losers))
    losers = list(filter(warrant_criteria, losers))

    losers = losers[:top_n]

    print(f"top {len(losers)} after applying criteria")
    print_losers_csv(losers)

    #
    # Buy losers
    #

    nominal = None
    if use_geometric:
        account = get_account()
        # TODO: figure out leverage for overnight positions
        effective_cash = float(account["cash"]) * cash_percent_to_use
        nominal = effective_cash / len(losers)
    else:
        nominal = base_nominal
        # TODO: check purchasing power in case need to reduce quantity

    order_intentions = []
    for loser in losers:
        quantity = round((nominal / loser['c']) - 0.5)  # round down

        symbol = loser['T']
        price = loser['c']
        print(
            f"Submitting buy order of {symbol} {quantity} (current price {price}, target amount {quantity * price}) at close")

        order_intentions.append({
            # use current time but same day
            "datetime": datetime.now().replace(year=today.year, month=today.month, day=today.day),
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "side": "buy"
        })
        try:
            buy_symbol_at_close(symbol, quantity)
        except Exception as e:
            print(e.response.status_code, e.response.json())
    return order_intentions


def record_intentions(today, order_intentions):
    if DRY_RUN:
        print("DRY_RUN: not writing order intentions (may overwrite)")
        return

    from src.pathing import get_order_intentions_csv_path
    path = get_order_intentions_csv_path(today)

    with open(path, "w") as f:
        f.write("Date,Time,Symbol,Quantity,Price,Side\n")

        for order_intention in order_intentions:
            now = order_intention['datetime'].astimezone(MARKET_TZ)
            ticker = order_intention['symbol']
            quantity = order_intention['quantity']
            price = order_intention['price']
            side = order_intention['side']
            s = f"{now.strftime('%Y-%m-%d')},{now.strftime('%H:%M:%S')},{ticker},{quantity},{round(price, 4)},{side.upper()}\n"
            f.write(s)


if __name__ == '__main__':
    today = date.today()

    import sys

    # buy or sell logic
    action = sys.argv[1]
    valid_actions = ['buy', 'sell']
    if action not in valid_actions:
        print(f"invalid action, must be one of {valid_actions}")
        exit(1)

    # allow reading `today` from CLI $2
    datestr = ""
    try:
        datestr = sys.argv[2]
    except:
        pass

    if datestr:
        try:
            today = datetime.strptime(datestr, '%Y-%m-%d').date()
        except Exception as e:
            print(
                f"error occurred while parsing datetime, will continue with {today}", e)

    print(f"running on date {today} with action {action}")

    if is_skipped_day(today):
        print("skipping day")
        exit(0)

    if action == 'buy':
        order_intentions = buy_biggest_losers_at_close(today)
        # write order intentions to file so we can evaluate slippage later
        record_intentions(today, order_intentions)
    elif action == 'sell':
        for position in get_positions():
            print(sell_symbol_at_open(
                position['symbol'], position['qty']))
