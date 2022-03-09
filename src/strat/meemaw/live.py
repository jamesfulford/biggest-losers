
"""
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
- [X] assert PDT
- [x] make sure that the account is day-trade-able. (at least 25K margin account)
- [x] TD: cancel all orders
- [x] add limit order support for brokers

- [ ] 5% up limit order (wait for order to fill? or place bracket order?)
- [ ] only play when entry is good (VWAP, RSI/ema crossings)
- [ ] sizing: 100% of account for margin
- [ ] sizing: 20% (?) of account for cash
- [ ] limit-thru entry orders (buffer needs to be better than 0.05)
- [ ] limit-thru exit orders (at 12pm)
- [ ] enable pre-market trading
- [ ] sell at 9:38? don't start until 9:38? (Mummy)
- [ ] when symbol falls off the scanner, do we sell immediately? (default: no)
- [ ] play more than 1 ticker at a time? (if so, how does sizing work?)

Questions We Have to be Answers By Data
- how often do members of the list change? (how many total stocks show up from 9:30-12)
    - ANSWER: top 5 => 14 stocks
- what is best time to buy for max profit at end
- how should sizing work
    size down? 20, 15, 10, 5...
- when is optimal sell time (not 12pm? 11? 10:30?)
- impactof penny stocks (<1, <.1, <.01)
- able to buy the dip?
"""

from datetime import time, timedelta
import logging
import sys
from time import sleep

from requests.exceptions import HTTPError
from src.broker.generic import get_open_orders
from src.strat.entries.market import buy_symbols
from src.strat.exits.oco import place_ocos
from src.strat.utils.pdt import assert_pdt
from src.strat.utils.scanners import get_scanner

from src.trading_day import now, today
from src.wait import get_next_minute_mark, wait_until

from src.broker.generic import get_positions


ALGO_NAME = "meemaw"


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


def execute_phases(scanner: str):
    next_minute = get_next_minute_mark(now())

    # Preparation Phase
    wait_until(next_minute - timedelta(seconds=5))

    positions = get_positions()
    scan_for_tickers = get_scanner(scanner)

    # Execution Phase
    wait_until(next_minute)

    tickers = scan_for_tickers(today(), skip_cache=True)
    tickers = tickers[:1]

    symbols_added_set = buy_symbols(f"{ALGO_NAME}_{scanner}", tickers,
                                    positions=positions, metadata={})

    if symbols_added_set:
        # TODO: push this to a separate thread so we don't block scanning or other logic or hold up
        while True:
            open_orders = get_open_orders()
            open_orders = [o for o in open_orders if o['symbol']
                           in symbols_added_set]
            if not open_orders:
                # all orders submitted earlier are now filled
                break
            logging.info(
                f"Waiting for {len(open_orders)} orders to fill ({symbols_added_set})")
            sleep(1)

        place_ocos(up=1.01, down=0.95)


def main():
    assert_pdt()

    scanner = sys.argv[1]
    logging.info(f"Starting live scanning with scanner '{scanner}'")
    loop(scanner)


if __name__ == "__main__":
    main()
