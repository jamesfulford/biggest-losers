from datetime import datetime
from analyze import is_warrant

from broker import buy_symbol_at_close, get_positions, liquidate
from grouped_aggs import get_spy_change
from losers import get_biggest_losers


def buy_biggest_losers_at_close(today):
    #   all rank  intr<-10  * spy  $50k vol  p < 5  no w                 | a_roi=4.326 g_roi=2.879 plays=481 avg_roi=0.016 win%=0.549 days=191

    acceptable_days = [0, 1, 2, 3, 4]
    dollar_volume_min = 50000
    closing_price_max = 5.00
    intraday_change_max = -0.10  # loss of 10% or greater loss (lesser number)
    rank_max = 20  # basically any rank
    spy_change_upper_threshold = 1.00  # basically no limit
    def warrant_criteria(c): return not is_warrant(c["T"])  # no warrants

    use_geometric = False

    losers = get_biggest_losers(today) or []

    for loser in losers:
        print(loser)

    weekday = today.weekday()  # 0 is Monday, 4 is Friday
    if weekday not in acceptable_days:
        print(f"today is not a good day for trading, clearing ticker list.")
        losers = []

    spy_change = get_spy_change(today)
    if spy_change > spy_change_upper_threshold:
        print(
            f"SPY change is {round(100*spy_change, 1)}%, must be under {round(100*spy_change_upper_threshold, 1)}%, clearing ticker list.")
        losers = []

    losers = list(filter(lambda l: l["v"] *
                  l["c"] > dollar_volume_min, losers))
    losers = list(filter(lambda l: l["c"] < closing_price_max, losers))
    losers = list(
        filter(lambda l: ((l["c"] - l["o"]) / l["o"]) < intraday_change_max, losers))
    losers = list(filter(lambda l: l["rank"] <= rank_max, losers))
    losers = list(filter(warrant_criteria, losers))

    positions = get_positions()
    print('DEBUG: current positions', positions)

    if use_geometric:
        print("have not implemented geometric, exiting")
        return

    # arithmetic - buy nominal amount of each loser
    # equal weighting

    nominal = 1000
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
