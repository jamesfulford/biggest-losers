
"""
Scan:
When to start? (Alpaca allows 4am, TD allows 7am)
- 100k? (for data collection)
- < $5
- sort by volume/float ratio
- TAKE TOP 5 (or less)

Entry:
- limit-thru order (buffer needs to be better than 0.05), allow premarket
- DATA: 1 share
- later: 20% (100%/5)

NEED TO COLLECT DATA, need to keep order intentions

Exit:
- 5% up take-profit
- Sell all at 12pm (cancel orders, liquidate positions)
- Sell if falls off scanner?


- [X] Do scanning
- [X] Make sure buying stock don't already own
- [X] Record intentions
- [X] Buy stocks on list
- [X] selling: cancel all orders
- [X] selling: sell all positions
- [X] tire out the dog
- [X] crontab entry start at 9:30am,
- [X] stop at 11:59am
- [X] crontab entry for meemaw-prepare
- [X] crontab clear_acount for 12pm (noon)
- [X] hook up to alpaca paper
- [X] fill in is_stock cache

- [ ] 5% up bracket profit
- [ ] add limit orders (to support premarket)
- [ ] sizing? 20% of account?
- [ ] sell at 9:38?
- [ ] falls off the list, do we sell then, at 12pm, or at +5%
- [ ] if buy, up 5%, sell, does it buy back if it shows back up on the list? go up 5, sell, buy, go up 5, sell, buy, etc.
- [ ] make sure that the account is day-trade-able. (at least 25K margin account)
- [ ] TD: cancel all orders
- [ ] schedule cache updating beforehand
- [ ]

Questions We Have to be Answers By Data
- how often do members of the list change? (how many total stocks show up from 9:30-12)
- what is best time to buy for max profit at end
- how should sizing work
    size down? 20, 15, 10, 5...
- when is optimal sell time (not 12pm? 11? 10:30?)
- impactof penny stocks (<1, <.1, <.01)
- able to buy the dip?
"""

from datetime import datetime, time, timedelta
import logging
from importlib import import_module

from requests.exceptions import HTTPError
from src.intention import log_intentions

from src.trading_day import now, today
from src.wait import wait_until

from src.broker.generic import buy_symbol_market, get_positions


ALGO_NAME = "meemaw"


def next_minute_mark(dt: datetime) -> datetime:
    return dt - timedelta(microseconds=dt.microsecond, seconds=dt.second) + timedelta(minutes=1)


def should_continue():
    return now().time() < time(12, 0)


def loop(scanner: str):
    while should_continue():
        try:
            execute_phases(scanner)
        except HTTPError as e:
            logging.exception(
                f"HTTP {e.response.status_code} {e.response.text}")
        except Exception as e:
            logging.exception(f"Unexpected Exception")


def format_price(price: float):
    if price < 1.:
        return f"{price:.4f}".replace("0.", ".")
    else:
        return f"{price:.2f}" + "  "


def execute_phases(scanner: str):
    next_interval_start = next_minute_mark(now())

    #
    # Preparation Phase
    #
    wait_until(next_interval_start - timedelta(seconds=5))
    positions = get_positions()
    current_symbols = set()

    for position in positions:
        current_symbols.add(position["symbol"])

    #
    # Execution Phase
    #
    wait_until(next_interval_start)
    # NOTE: Cache for multiple previous days must be prepared beforehand in order to work.
    day = today()

    module = import_module("src.scan." + scanner)
    tickers = module.get_all_candidates_on_day(day, skip_cache=True)

    desired_symbols = set()
    for ticker in tickers[:5]:
        desired_symbols.add(ticker["T"])

    symbols_to_add = desired_symbols.difference(current_symbols)

    intentions = []
    for symbol in symbols_to_add:
        # find ticker {} given symbol str
        ticker = next(filter(lambda t: t['T'] == symbol, tickers))

        # TODO: sizing
        target_quantity = 1
        intentions.append({
            "datetime": now(),
            "symbol": ticker["T"],
            "price": ticker['c'],
            "side": "buy",
            "quantity": target_quantity,

            "volume": ticker['v'],
            "float": ticker['float'],
            "float_vol_percent": round(ticker['v']/ticker['float'], 3),
            "percent_change": round(ticker["percent_change"], 3),
        })
        buy_symbol_market(symbol, target_quantity)

    if intentions:
        metadata = {
            # TODO: add more metadata when we do sizing
        }
        log_intentions(ALGO_NAME, intentions, metadata)


def main():
    import sys

    scanner = sys.argv[1]
    assert scanner.replace("_", "").isalpha()

    logging.info(f"Starting live scanning with scanner '{scanner}'")
    loop(scanner)


if __name__ == "__main__":
    main()
