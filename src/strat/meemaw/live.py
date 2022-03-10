
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
- [x] 2% up limit order (wait for order to fill)
- [x] only play when entry is good (VWAP, RSI/sma crossings)
- [x] short interest: previous_report_date=None handling (assume 32 days, remove log)
- [x] update reporting scripts to join intentions and orders
- [ ] sizing: 100% of account for margin
- [ ] sizing: 20% (?) of account for cash
- [ ] limit-thru entry orders (buffer needs to be better than 0.05)
- [ ] limit-thru exit orders (at 3:59pm)
- [ ] enable pre-market trading
- [ ] don't start until 9:38? (Mummy)
- [ ] when symbol falls off the scanner, do we sell immediately? (default: no)
- [ ] play more than 1 ticker at a time? (if so, how does sizing work?)

Questions We Have to be Answers By Data
- how often do members of the list change? (how many total stocks show up from 9:30-12)
    - top 5 => 14 stocks
    - top 1 (with vwap requirement) => 12
    - top 1 => ???
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
import numpy as np
import pandas as pd
from talib.abstract import RSI

from requests.exceptions import HTTPError
import ta
from src.broker.generic import get_open_orders
from src.data.finnhub.finnhub import get_candles
from src.strat.entries.market import buy_symbols
from src.strat.exits.oco import place_ocos
from src.strat.meemaw.settle import await_buy_order_settling
from src.strat.utils.pdt import assert_pdt
from src.strat.utils.scanners import get_scanner

from src.trading_day import now, previous_trading_day, today
from src.wait import get_next_minute_mark, wait_until

from src.broker.generic import get_positions


ALGO_NAME = "meemaw"


def should_continue():
    return now().time() < time(15, 59)


def loop(scanner: str):
    while should_continue():
        try:
            execute_phases(scanner)
        except HTTPError as e:
            logging.exception(
                f"HTTP {e.response.status_code} {e.response.text}")
        except Exception as e:
            logging.exception(f"Unexpected Exception")


def get_vwap(candles):
    candles = list(filter(lambda c: c['datetime'].date(
    ) == candles[-1]['datetime'].date(), candles))
    highs = pd.Series(list(map(lambda c: float(c["high"]), candles)))
    lows = pd.Series(list(map(lambda c: float(c["low"]), candles)))
    closes = pd.Series(list(map(lambda c: float(c["close"]), candles)))
    volumes = pd.Series(list(map(lambda c: float(c["volume"]), candles)))
    values = ta.volume.volume_weighted_average_price(
        highs, lows, closes, volumes)
    return values.tolist()[-1]


def get_rsi_and_sma(candles, timeperiod=14, sma_period=20):
    # try to save some calculations by not using all candles
    minimum_candles_needed = timeperiod + sma_period
    candles = candles[-minimum_candles_needed:]
    inputs = {
        "open": np.array(list(map(lambda c: float(c["open"]), candles))),
        "high": np.array(list(map(lambda c: float(c["high"]), candles))),
        "low": np.array(list(map(lambda c: float(c["low"]), candles))),
        "close": np.array(list(map(lambda c: float(c["close"]), candles))),
        "volume": np.array(list(map(lambda c: float(c["volume"]), candles))),
    }
    rsi_line = RSI(inputs, timeperiod=timeperiod)
    rsi_sma = np.mean(rsi_line[-sma_period:])

    return rsi_line[-1], rsi_sma


def execute_phases(scanner: str):
    rsi_overbought_level = 80

    next_minute = get_next_minute_mark(now())

    # Preparation Phase
    wait_until(next_minute - timedelta(seconds=5))

    positions = get_positions()
    scan_for_tickers = get_scanner(scanner)

    # Execution Phase
    wait_until(next_minute)

    day = today()
    tickers = scan_for_tickers(day, skip_cache=True)
    tickers = tickers[:1]

    new_tickers = []
    for ticker in tickers:
        candles_1m = get_candles(ticker["T"], "1", previous_trading_day(
            previous_trading_day(day)), day)

        ticker['vwap_1m'] = get_vwap(candles_1m)
        ticker['rsi'], ticker['rsi_sma'] = get_rsi_and_sma(candles_1m)

        # Above the VWAP on 1m chart
        if not (ticker['c'] > ticker['vwap_1m']):
            logging.info(
                f"{ticker['T']} is below 1m VWAP ({ticker['c']} < {ticker['vwap_1m']})")
            continue

        if np.isnan(ticker['rsi']) or np.isnan(ticker['rsi_sma']):
            logging.info(
                f"{ticker['T']} is has nan RSI value: {ticker['rsi']=} {ticker['rsi_sma']=}")
            continue
        if not (ticker['rsi'] < rsi_overbought_level):
            logging.info(
                f"{ticker['T']} is overbought on RSI ({ticker['rsi']} > {rsi_overbought_level})")
            continue
        if not (ticker['rsi'] > ticker['rsi_sma']):
            logging.info(
                f"{ticker['T']} is under RSI SMA ({ticker['rsi']} < {ticker['rsi_sma']})")
            continue

        new_tickers.append(ticker)
    tickers = new_tickers

    symbols_added_set = buy_symbols(ALGO_NAME, tickers,
                                    positions=positions, metadata={
                                        "scanner": scanner,
                                    })

    if symbols_added_set:
        await_buy_order_settling(symbols_added_set)
        place_ocos(up=1.02, down=0.94)


def main():
    assert_pdt()

    scanner = sys.argv[1]
    logging.info(f"Starting live scanning with scanner '{scanner}'")
    loop(scanner)


if __name__ == "__main__":
    main()
