from src.criteria import is_etf, is_right, is_stock, is_unit, is_warrant
from src.trading_day import today
import logging


def main():
    logging.info("Started updating symbol details cache")

    is_stock("AAPL", day=today())
    is_etf("SPY", day=today())
    is_warrant("ADRW", day=today())
    is_right("ADRR", day=today())
    is_unit("ADRU", day=today())

    logging.info("Ending updating symbol details cache")


if __name__ == "__main__":
    main()
