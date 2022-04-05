import logging
from typing import Set
from src.broker.alpaca import get_account
from src.entries.sizing import allocate_cash, exponential_apportionment, size_shares_from_allocation
from src.trading_day import now
from src.broker.generic import get_positions, buy_symbol_market
from src.outputs.intention import log_intentions


def buy_symbols(algo_name: str, tickers: list,
                metadata=None,
                single_share: bool = False, exponential_apportionment_ratio: float = 0.75,
                positions=None, account=None,
                ) -> Set[str]:
    """
    Buy the given tickers if not already owned.
    - market orders
    - use 75% of cash for first unowned ticker, 18.75% for second (75% of remainder), etc.
    """
    if not tickers:
        return set()

    if not metadata:
        metadata = {}

    if positions is None:
        positions = get_positions()

    if account is None:
        account = get_account()

    current_symbols = set()
    for position in positions:
        current_symbols.add(position["symbol"])

    desired_symbols = set()
    for ticker in tickers:
        desired_symbols.add(ticker["T"])
    logging.info(f"Tickers found by scan: {desired_symbols}")

    symbols_to_add = desired_symbols.difference(current_symbols)

    if not symbols_to_add:
        return set()

    tickers_to_add = list(
        filter(lambda ticker: ticker["T"] in symbols_to_add, tickers))

    # TODO: allow for different allocation methods
    apportionment = exponential_apportionment(
        exponential_apportionment_ratio, depth=len(tickers_to_add))
    allocation = allocate_cash(account, apportionment)

    prices = [ticker["c"] for ticker in tickers_to_add]
    target_shares = size_shares_from_allocation(
        allocation, prices, at_least_shares=1, at_most_shares=1 if single_share else None)

    intentions = [
        {
            "datetime": now(),
            "symbol": ticker["T"],
            "price": ticker['c'],
            "side": "buy",
            "quantity": target_quantity,

            "ticker": ticker,
        }
        for ticker, target_quantity in zip(tickers_to_add, target_shares)
    ]

    logging.info(f"Tickers not yet owned: {desired_symbols}")

    for intention in intentions:
        symbol = intention['symbol']
        target_quantity = intention['quantity']
        buy_symbol_market(symbol, target_quantity)

    log_intentions(algo_name, intentions, metadata)

    return symbols_to_add
