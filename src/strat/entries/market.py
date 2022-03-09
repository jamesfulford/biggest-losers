import logging
from typing import Set
from src.trading_day import now
from src.broker.generic import get_positions, buy_symbol_market
from src.intention import log_intentions


def buy_symbols(algo_name: str, tickers: list, positions=None, metadata=None) -> Set[str]:
    if not tickers:
        return

    if not metadata:
        metadata = {}

    if positions is None:
        positions = get_positions()

    current_symbols = set()
    for position in positions:
        current_symbols.add(position["symbol"])

    desired_symbols = set()
    for ticker in tickers:
        desired_symbols.add(ticker["T"])
    logging.info(f"Tickers found by scan: {desired_symbols}")

    symbols_to_add = desired_symbols.difference(current_symbols)
    logging.info(f"Tickers not yet owned: {desired_symbols}")

    intentions = []
    for symbol in symbols_to_add:
        # find ticker {} given symbol str
        ticker = next(filter(lambda t: t['T'] == symbol, tickers))

        # TODO: sizing logic and config (include details in intentions or metadata)
        target_quantity = 1
        intentions.append({
            "datetime": now(),
            "symbol": ticker["T"],
            "price": ticker['c'],
            "side": "buy",
            "quantity": target_quantity,

            "ticker": ticker,
        })
        buy_symbol_market(symbol, target_quantity)

    if intentions:
        log_intentions(algo_name, intentions, metadata)

    return symbols_to_add
