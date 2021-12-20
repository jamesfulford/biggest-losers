from datetime import date, datetime

from src.broker.generic import buy_symbol_at_close, get_account, get_positions, sell_symbol_at_open
from src.losers import get_biggest_losers
from src.criteria import is_skipped_day


def buy_biggest_losers_at_close(today: date, minimum_loss_percent=0.1, closing_price_min=0.0, minimum_volume=0, minimum_dollar_volume=0, top_n=10, warrant_criteria=lambda _: True, cash_percent_to_use=0.9):
    """
    minimum_loss_percent = 0.1  # down at least 10%; aka percent_change < -0.1

    closing_price_min = 0.0  # no price requirement
    minimum_volume = 0  # no volume requirement, let's see how we do

    def warrant_criteria(c): return not is_warrant(c["T"])

    top_n = 10

    # to simulate cash settling, do .33. That's using 1/3 of cash every night.
    # 1.0 is using all cash every night.
    # higher will start using margin. Overnight margin has special rules, max is probably near 1.5 as far as I can tell
    cash_percent_to_use = 1.0
    """
    if is_skipped_day(today):
        print("skipping day")
        return
    #
    # Filter losers
    #

    losers = get_biggest_losers(today, bust_cache=True, top_n=1000) or []
    losers = list(
        filter(lambda l: l["percent_change"] < -minimum_loss_percent, losers))

    losers = list(filter(lambda l: l["c"] > closing_price_min, losers))
    losers = list(filter(lambda l: l["v"] > minimum_volume, losers))
    losers = list(filter(lambda l: l["v"] *
                  l['c'] > minimum_dollar_volume, losers))
    losers = list(filter(warrant_criteria, losers))

    losers = losers[:top_n]

    #
    # Buy losers
    #

    account = get_account()
    effective_cash = float(account["cash"]) * cash_percent_to_use
    nominal = effective_cash / len(losers)

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
            "side": "buy",
            # TODO: pass back various account balances here
        })
        try:
            buy_symbol_at_close(symbol, quantity)
        except Exception as e:
            print(e.response.status_code, e.response.json())
    return order_intentions


def sell_biggest_losers_at_open(today: date):
    if is_skipped_day(today):
        print("skipping day")
        return

    for position in get_positions():
        sell_symbol_at_open(
            position['symbol'], position['qty'])
