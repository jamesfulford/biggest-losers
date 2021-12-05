from datetime import datetime

from broker import buy_symbol_at_close, get_positions, liquidate
from losers import get_biggest_losers


def print_losers_csv(losers):
    cols = sorted(losers[0].keys())
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
    closing_price_min = 3.00
    rank_max = 10  # top 10
    def warrant_criteria(c): return True  # can be warrants
    use_geometric = False

    #
    # Filter losers
    #

    losers = get_biggest_losers(today, bust_cache=True) or []

    print_losers_csv(losers)

    losers = list(filter(lambda l: l["c"] > closing_price_min, losers))
    losers = list(filter(lambda l: l["rank"] <= rank_max, losers))
    losers = list(filter(warrant_criteria, losers))

    print("after applying criteria")
    print_losers_csv(losers)

    print_current_positions()

    #
    # Buy losers
    #

    if use_geometric:
        print("have not implemented geometric, exiting")
        return

    # arithmetic - buy nominal amount of each loser
    # equal weighting

    nominal = 10000
    # TODO: check purchasing power in case need to reduce quantity

    for loser in losers:
        quantity = round((nominal / loser['c']) - 0.5)
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
