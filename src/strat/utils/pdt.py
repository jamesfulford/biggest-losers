import logging
from typing import Union
from src.broker.generic import get_account


def assert_pdt(account: Union[dict, None] = None):
    if account is None:
        account = get_account()
    logging.info(f"Checking day-trading algos can be run in this account...")
    assert account["type"] == "CASH" or account["equity"] > 25000, "Either use a cash account or fund margin account with $25k+ equity to avoid PDT violations."
    logging.info(f"Account is OK.")
