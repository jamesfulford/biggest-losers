from src.broker.generic import cancel_all_orders, get_positions, sell_symbol_market


def main():
    cancel_all_orders()
    positions = get_positions()

    for position in positions:
        sell_symbol_market(position["symbol"], position["qty"])


if __name__ == "__main__":
    main()
