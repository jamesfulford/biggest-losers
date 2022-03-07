
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

from datetime import datetime, time, timedelta
import logging
import sys

from requests.exceptions import HTTPError
from src.intention import log_intentions
from src.strat.utils.pdt import assert_pdt
from src.strat.utils.scanners import get_scanner

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

    scan_for_tickers = get_scanner(scanner)

    #
    # Execution Phase
    #
    wait_until(next_interval_start)
    # NOTE: Cache for multiple previous days must be prepared beforehand in order to work.
    day = today()

    tickers = scan_for_tickers(day, skip_cache=True)

    # we want only top 1
    tickers = tickers[:1]

    desired_symbols = set()
    for ticker in tickers:
        desired_symbols.add(ticker["T"])

    logging.info(f"Desired Symbols: {desired_symbols}")

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
    assert_pdt()

    scanner = sys.argv[1]
    logging.info(f"Starting live scanning with scanner '{scanner}'")
    loop(scanner)


if __name__ == "__main__":
    main()
