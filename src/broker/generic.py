import logging
import os


broker_name = os.environ.get('BROKER')

if broker_name == "alpaca":
    import src.broker.alpaca as alpaca
    buy_symbol_at_close = alpaca.buy_symbol_at_close
    sell_symbol_at_open = alpaca.sell_symbol_at_open

    buy_symbol_market = alpaca.buy_symbol_market
    sell_symbol_market = alpaca.sell_symbol_market
    buy_limit = alpaca.buy_limit
    sell_limit = alpaca.sell_limit
    buy_limit_thru = alpaca.buy_limit_thru
    sell_limit_thru = alpaca.sell_limit_thru

    get_account = alpaca.get_account
    get_positions = alpaca.get_positions
    get_filled_orders = alpaca.get_filled_orders

    cancel_all_orders = alpaca.cancel_all_orders
elif broker_name == "td":
    import src.broker.td as td
    buy_symbol_at_close = td.buy_symbol_at_close
    sell_symbol_at_open = td.sell_symbol_at_open

    buy_symbol_market = td.buy_symbol_market
    sell_symbol_market = td.sell_symbol_market
    buy_limit = td.buy_limit
    sell_limit = td.sell_limit
    buy_limit_thru = td.buy_limit_thru
    sell_limit_thru = td.sell_limit_thru

    get_account = td.get_account
    get_positions = td.get_positions
    get_filled_orders = td.get_filled_orders

    cancel_all_orders = td.cancel_all_orders
elif broker_name == "pizzalabs":
    import src.broker.pizzalabs as pizzalabs
    buy_symbol_at_close = pizzalabs.buy_symbol_at_close
    sell_symbol_at_open = pizzalabs.sell_symbol_at_open

    buy_symbol_market = pizzalabs.buy_symbol_market
    sell_symbol_market = pizzalabs.sell_symbol_market
    buy_limit = pizzalabs.buy_limit
    sell_limit = pizzalabs.sell_limit
    buy_limit_thru = pizzalabs.buy_limit_thru
    sell_limit_thru = pizzalabs.sell_limit_thru

    get_account = pizzalabs.get_account
    get_positions = pizzalabs.get_positions
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
