import logging
import sys
from src.entries.market import buy_symbols
from src.strat.meemaw.settle import await_buy_order_settling
from src.scan.utils.scanners import get_scanner

import os

ALGO_NAME = os.environ.get("ALGO_NAME", "scan_and_buy_market")


#
# Buys the symbols returned by scanner if not already owned.
#
def main():
    scanner = sys.argv[1]
    logging.info(f"Scanning with scanner '{scanner}'...")

    tickers = get_scanner(scanner)()

    # TODO: equal apportionment for all tickers
    symbols = buy_symbols(ALGO_NAME, tickers,
                          metadata={"scanner": scanner},
                          exponential_apportionment_ratio=0.99)
    logging.info(f"Symbols bought: {symbols}")
    if symbols:
        await_buy_order_settling(symbols)
