
import logging
from math import floor

# Sizing strategy:
# - shares I want = equity * percentage / price

# error case: shares I want computes to 0 because of percentage
# - if shares is 0, then try 1 (minimum shares)

# error case: shares I want computes to infinity because I'm incredibly rich (10,000 a year, and likely more!)
# - put a limit

# error case: not enough cash to buy
# - then, try to get as close to target shares as possible
# - this is a hard limit, so no other logic should override this


def size_buy(account, equity_percentage: float, asset_price: float, at_most_shares: int = None, at_least_shares: int = None) -> int:
    equity_shares = account["equity"] / asset_price
    target_shares = floor(equity_shares * equity_percentage)

    shares = target_shares

    if at_most_shares is not None and shares > at_most_shares:
        logging.info(
            f"at_most_shares: reduced {shares} shares to {at_most_shares} shares.")
        shares = at_most_shares

    if at_least_shares is not None and shares < at_least_shares:
        logging.info(
            f"at_least_shares: increased {shares} shares to {at_least_shares} shares.")
        shares = at_least_shares

    # make sure we don't buy more than we can afford
    purchaseable_shares = floor(account["cash"] / asset_price)
    if shares > purchaseable_shares:
        logging.info(
            f"insufficient cash ({account['cash']}) to buy {shares} (${asset_price * shares}) shares. Reducing to {purchaseable_shares} (${asset_price * purchaseable_shares}).")
        shares = purchaseable_shares

    return shares


def main():
    # 20% of 100 is 20, not enough to buy a $21 share
    assert size_buy({"cash": 100, "equity": 100}, .2, 21.0) == 0
    assert size_buy({"cash": 100, "equity": 100}, .2, 21.0,
                    at_least_shares=1) == 1  # even if not enough, buy 1
    assert size_buy({"cash": 20, "equity": 100}, .2, 21.0,
                    at_least_shares=1) == 0  # ...unless we can't afford it
