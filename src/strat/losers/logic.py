from datetime import date, datetime
import json
import logging

from src.broker.generic import buy_symbol_at_close, get_account, get_positions, sell_symbol_at_open
from src.scan.losers import get_all_candidates_on_day
from src.data.polygon.asset_class import is_skipped_day


def buy_biggest_losers(
    today: date,
    minimum_loss_percent=0.1,
    closing_price_min=0.0,
    minimum_volume=0,
    minimum_dollar_volume=0,
    top_n=10,
    warrant_criteria=lambda _: True,
    cash_percent_to_use=0.9,
    buy_function=lambda symbol, quantity: buy_symbol_at_close(symbol, quantity)
):
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
        logging.warning("skipping day")
        return
    #
    # Filter losers
    #

    losers = get_all_candidates_on_day(today) or []

    # NOTE: if we ever need multi-day averages, we will start to need the cache to be filled
    # with enough days. If not careful, might use data with different adjustment base
    # if stock split is done between caching and live run
    # (like if a $10 becomes $5 due to split, cache will say $10 and
    # 100EMA might be computed to be $9.83, but not adjusted for most recent split)

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
    nominal = effective_cash / len(losers) if losers else 0

    order_intentions = []
    for loser in losers:
        quantity = round((nominal / loser['c']) - 0.5)  # round down

        symbol = loser['T']
        price = loser['c']
        print(
            f"Submitting buy order of {symbol} {quantity} (current price {price}, target amount {quantity * price}) at close")

        account_before = get_account()
        print("account before:", json.dumps(account_before))
        order_intentions.append({
            # use current time but same day, in case of testing with overriding date
            "datetime": datetime.now().replace(year=today.year, month=today.month, day=today.day),
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "side": "buy",
            # account balance before order
            "cash_before": account_before["cash"],
        })

        try:
            buy_function(symbol, quantity)
        except Exception as e:
            print(e.response.status_code, e.response.raw.read())
        print("account after:", json.dumps(get_account()))
    return order_intentions


def sell_biggest_losers_at_open(today: date):
    if is_skipped_day(today):
        print("skipping day")
        return

    for position in get_positions():
        print(sell_symbol_at_open(
            position['symbol'], position['qty']))
