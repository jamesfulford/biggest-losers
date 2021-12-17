import os


broker_name = os.environ.get('BROKER', "td")

if broker_name == "alpaca":
    import src.broker.alpaca as alpaca
    buy_symbol_at_close = alpaca.buy_symbol_at_close
    sell_symbol_at_open = alpaca.sell_symbol_at_open
    get_positions = alpaca.get_positions
    get_account = alpaca.get_account
    get_filled_orders = alpaca.get_filled_orders
elif broker_name == "td":
    import src.broker.td as td
    buy_symbol_at_close = td.buy_symbol_market
    sell_symbol_at_open = td.sell_symbol_at_open
    get_positions = td.get_positions
    get_account = td.get_account
    get_filled_orders = td.get_filled_orders
