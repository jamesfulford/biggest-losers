import logging
logging.warn(
    "YOU'RE IN PIZZA LABS NOW! YOU CAN CHECK OUT, BUT YOU CAN NEVER LEAVE!")


def buy_symbol_at_close(*args, **kwargs):
    logging.info(f"buy_symbol_at_close: {args=} {kwargs=}")


def buy_symbol_market(*args, **kwargs):
    logging.info(f"buy_symbol_market: {args=} {kwargs=}")


def sell_symbol_market(*args, **kwargs):
    logging.info(f"sell_symbol_market: {args=} {kwargs=}")


def sell_symbol_at_open(*args, **kwargs):
    logging.info(f"sell_symbol_at_open: {args=} {kwargs=}")


def get_positions(*args, **kwargs):
    logging.info(f"get_positions: {args=} {kwargs=}")
    return []


def get_account(*args, **kwargs):
    logging.info(f"get_account: {args=} {kwargs=}")
    return {
        "type": "MARGIN",
        "equity": 1337000,
        "cash": 1337000,
    }


def get_filled_orders(*args, **kwargs):
    logging.info(f"get_filled_orders: {args=} {kwargs=}")


def cancel_all_orders() -> None:
    logging.info(f"Canceled all orders")


def buy_limit(*args, **kwargs):
    logging.info(f"buy_limit: {args=} {kwargs=}")


def sell_limit(*args, **kwargs):
    logging.info(f"sell_limit: {args=} {kwargs=}")


def place_oco(*args, **kwargs):
    logging.info(f"place_oco: {args=} {kwargs=}")


def get_open_orders(*args, **kwargs):
    logging.info(f"get_open_orders: {args=} {kwargs=}")
    return []
