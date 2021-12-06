from datetime import datetime

from broker import buy_symbol_at_close, get_account, get_positions, liquidate
from losers import get_biggest_losers
from criteria import is_warrant


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

    closing_price_min = 3.00
    minimum_volume = 1000000  # at least 1 million
    def warrant_criteria(c): return not is_warrant(c["T"])

    top_n = 10

    use_geometric = True

    # geometric
    # to simulate cash settling, do .33. That's using 1/3 of cash every night.
    # 1.0 is using all cash every night.
    # higher will start using margin. Overnight margin has special rules, max is probably near 1.5 as far as I can tell
    cash_percent_to_use = 0.95

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

    for loser in losers:
        quantity = round((nominal / loser['c']) - 0.5)  # round down
        print(
            f"Submitting buy order of {loser['T']} {quantity} (current price {loser['c']}, target amount {quantity * loser['c']}) at close")
        try:
            buy_symbol_at_close(loser["T"], quantity)
        except Exception as e:
            print(e.response.status_code, e.response.json())


if __name__ == '__main__':
    today = datetime.today()

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

    if action == 'buy':
        buy_biggest_losers_at_close(today)
    elif action == 'sell':
        print(liquidate())
