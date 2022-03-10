import logging
import sys
from src.strat.entries.market import buy_symbols
from src.strat.meemaw.settle import await_buy_order_settling
from src.strat.utils.scanners import get_scanner
from src.trading_day import today

ALGO_NAME = "scan_and_buy_market"


#
# Buys the symbols returned by scanner if not already owned.
#
def main():
    scanner = sys.argv[1]
    logging.info(f"Scanning with scanner '{scanner}'...")

    tickers = get_scanner(scanner)(today(), skip_cache=True)

    symbols = buy_symbols(f"{ALGO_NAME}_{scanner}", tickers,
                          metadata={"scanner": scanner})
    await_buy_order_settling(symbols)
