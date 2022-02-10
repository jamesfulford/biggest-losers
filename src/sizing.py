
import logging


def get_cash_to_use_for_percentage(account, percentage):
    target_amount = account["equity"] * percentage
    sized = min(target_amount, account["cash"])
    return sized


def get_shares(cash_to_use: float, price: float, single_share=False) -> int:
    shares = cash_to_use // price
    if single_share:
        logging.debug("using single share, would have done {shares} shares.")
        # if can afford 0 shares, use 0
        shares = min(shares, 1)
    return int(shares)


def size_buy(account, percentage: float, price: float, single_share=False) -> int:
    cash_to_use = get_cash_to_use_for_percentage(account, percentage)
    shares = get_shares(cash_to_use, price, single_share=single_share)
    return shares
