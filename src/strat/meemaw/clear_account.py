import logging
from src.broker.generic import cancel_all_orders, get_positions, sell_symbol_market


def main():
    logging.info("Cancelling all orders...")
    cancel_all_orders()

    logging.info("Liquidating all positions...")
    positions = get_positions()
    for position in positions:
        sell_symbol_market(position["symbol"], position["qty"])

    logging.info("Done.")


if __name__ == "__main__":
    main()
