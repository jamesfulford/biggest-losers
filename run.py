from datetime import datetime

from broker import buy_symbol_at_close, get_positions, liquidate
from grouped_aggs import get_spy_change
from losers import get_biggest_losers


def buy_biggest_losers_at_close(today):
    #   -1%spy       *vol    p < 5   all d   top 8   intr<-8 !w |roi=7.548 a_roi=7.548 g_roi=7.142 plays=227 avg_roi=0.04 win%=0.507 days=148

    weekday = today.weekday()  # 0 is Monday, 4 is Friday
    if weekday not in [0, 1, 2, 3, 4]:
        print(f"today is not a good day for trading, exiting.")
        return

    spy_change = get_spy_change(today)
    spy_change_upper_threshold = -.01
    if spy_change > spy_change_upper_threshold:
        print(
            f"SPY change is {round(100*spy_change, 1)}%, must be under {round(100*spy_change_upper_threshold, 1)}%, not buying")
        return

    losers = get_biggest_losers(today)
    if not losers:
        return None

    losers = list(filter(lambda l: l["v"] > 100000, losers))
    losers = list(filter(lambda l: l["c"] < 5, losers))
    losers = list(filter(lambda l: ((l["c"] - l["o"]) / l["o"]) < -8, losers))
    losers = list(filter(lambda l: l["rank"] <= 8, losers))

    positions = get_positions()
    print('DEBUG: current positions', positions)

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
    now = datetime.now()
    import sys
    datestr = ""
    try:
        datestr = sys.argv[1]
    except:
        pass

    if datestr:
        try:
            now = datetime.strptime(datestr, '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(
                f"error occurred while parsing datetime, will continue with {now}", e)

    today = now.date()
    hour = now.hour

    print(
        f"running on date {today} at hour {hour} in local timezone (should be America/New_York)")

    if hour >= 15 and hour < 16:
        print("3-4pm, buying biggest losers")
        buy_biggest_losers_at_close(today)
    elif hour >= 19 or hour < 15:
        print("closing positions")
        print(liquidate())
    else:
        print("not time to do anything yet")
