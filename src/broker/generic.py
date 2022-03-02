import logging
import os


broker_name = os.environ.get('BROKER')

if broker_name == "alpaca":
    import src.broker.alpaca as alpaca
    buy_symbol_at_close = alpaca.buy_symbol_at_close
    buy_symbol_market = alpaca.buy_symbol_market
    sell_symbol_market = alpaca.sell_symbol_market
    sell_symbol_at_open = alpaca.sell_symbol_at_open
    get_positions = alpaca.get_positions
    get_account = alpaca.get_account
    get_filled_orders = alpaca.get_filled_orders
    cancel_all_orders = alpaca.cancel_all_orders
elif broker_name == "td":
    import src.broker.td as td
    buy_symbol_at_close = td.buy_symbol_at_close
    buy_symbol_market = td.buy_symbol_market
    sell_symbol_market = td.sell_symbol_market
    sell_symbol_at_open = td.sell_symbol_at_open
    get_positions = td.get_positions
    get_account = td.get_account
    get_filled_orders = td.get_filled_orders
    # TODO: cancel all orders
elif broker_name == "pizzalabs":
    import src.broker.pizzalabs as pizzalabs
    buy_symbol_at_close = pizzalabs.buy_symbol_at_close
    buy_symbol_market = pizzalabs.buy_symbol_market
    sell_symbol_market = pizzalabs.sell_symbol_market
    sell_symbol_at_open = pizzalabs.sell_symbol_at_open
    get_positions = pizzalabs.get_positions
    get_account = pizzalabs.get_account
    get_filled_orders = pizzalabs.get_filled_orders
    cancel_all_orders = pizzalabs.cancel_all_orders
else:
    logging.fatal(f"BROKER '{broker_name}' not supported. Exiting...")
    exit(1)


def main():
    import src.broker.alpaca as alpaca
    import src.broker.td as td
    import json

    import logging
    logging.getLogger().setLevel(logging.DEBUG)

    print(json.dumps(td.get_positions(), indent=2, sort_keys=True))
    print(json.dumps(alpaca.get_positions(), indent=2, sort_keys=True))
    print()
