
import logging
from math import floor
from typing import Optional

# Sizing strategy:
# - shares I want = equity * percentage / price

# error case: shares I want computes to 0 because of percentage
# - if shares is 0, then try 1 (minimum shares)

# error case: shares I want computes to infinity because I'm incredibly rich (10,000 a year, and likely more!)
# - put a limit

# error case: not enough cash to buy
# - then, try to get as close to target shares as possible
# - this is a hard limit, so no other logic should override this


def size_buy(account: dict, cash_equity_percentage: float, asset_price: float, at_most_shares: Optional[int] = None, at_least_shares: Optional[int] = None) -> int:
    equity_percentage = 1.0 if account["type"] == "MARGIN" else cash_equity_percentage

    equity_shares = account["equity"] / asset_price
    target_shares = floor(equity_shares * equity_percentage)

    shares = normalize_target_shares(target_shares)

    # make sure we don't buy more than we can afford
    purchaseable_shares = floor(account["cash"] / asset_price)
    if shares > purchaseable_shares:
        logging.info(
            f"insufficient cash ({account['cash']}) to buy {shares} (${asset_price * shares}) shares. Reducing to {purchaseable_shares} (${asset_price * purchaseable_shares}).")
        shares = purchaseable_shares

    return shares


def normalize_target_shares(target_shares: int, at_most_shares: Optional[int] = None, at_least_shares: Optional[int] = None) -> int:
    if at_most_shares is not None and target_shares > at_most_shares:
        logging.info(
            f"at_most_shares: reduced {target_shares} shares to {at_most_shares} shares.")
        target_shares = at_most_shares

    if at_least_shares is not None and target_shares < at_least_shares:
        logging.info(
            f"at_least_shares: increased {target_shares} shares to {at_least_shares} shares.")
        target_shares = at_least_shares

    return target_shares


# Stable (roughly) across batches of trades:
# - equal apportionment, valued by equity ('Use 20% of the account for each stock')
# - exponential apportionment, valued by cash ('Use 60% of the available money for each stock, successively')

def exponential_apportionment(ratio: float, depth: int):
    # .7, .3*.7, .3*.3*.7
    return [ratio * ((1-ratio) ** (d-1)) for d in range(1, depth + 1)]


def equal_apportionment(depth: int):
    return [1.0 / depth] * depth


def allocate_cash(account: dict, apportionment: list[float]):
    return [account["cash"] * r for r in apportionment]


def allocate_equity_fifo(account: dict, apportionment: list[float]):
    """
    Allocates share of account's equity according to apportionment plan.
    When insufficient cash is available, the earlier apportionment values are prioritized.
    """
    cash_apportionment = []
    cash_available = account["cash"]
    for r in apportionment:
        value = min(r * account['equity'], cash_available)
        cash_available -= value
        cash_apportionment.append(value)

    return cash_apportionment


def allocate_equity_lifo(account: dict, apportionment: list[float]):
    """
    Allocates share of account's equity according to apportionment plan.
    When insufficient cash is available, the later apportionment values are prioritized.
    """
    return list(reversed(allocate_equity_fifo(account, list(reversed(apportionment)))))


def size_shares_from_allocation(allocation: list[float], prices: list[float], at_most_shares: Optional[int] = None, at_least_shares: Optional[int] = None) -> list[int]:
    target_shares_list = [floor(r / p) for r, p in zip(allocation, prices)]
    normalized_shares = [normalize_target_shares(
        s, at_most_shares=at_most_shares, at_least_shares=at_least_shares) for s in target_shares_list]
    return normalized_shares


def main():
    print(sum(exponential_apportionment(.75, 99999)))
