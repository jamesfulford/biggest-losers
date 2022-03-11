import logging
import sys
from src.strat.entries.market import buy_symbols
from src.strat.meemaw.settle import await_buy_order_settling
from src.strat.utils.scanners import get_scanner

import os

ALGO_NAME = os.environ.get("ALGO_NAME", "scan_and_buy_market")


#
# Buys the symbols returned by scanner if not already owned.
#
def main():
    scanner = sys.argv[1]
    logging.info(f"Scanning with scanner '{scanner}'...")

    tickers = get_scanner(scanner)()

    symbols = buy_symbols(f"{ALGO_NAME}", tickers,
                          metadata={"scanner": scanner})
    await_buy_order_settling(symbols)
