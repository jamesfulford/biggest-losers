import datetime
import typing
import src.broker.generic as broker
from src.broker.types import Account, FilledOrder


def main():
    filled_orders = broker.get_filled_orders(
        datetime.datetime(2022, 1, 1), datetime.datetime(2022, 5, 10))

    account = broker.get_account()

    d = datetime.date.today()
    for current_datetime, balance in order_simulate_balance(account, filled_orders):
        current_date = current_datetime.date()
        if current_date != d:
            print(current_date, round(balance, 2))
            d = current_date


def order_simulate_balance(account: Account, filled_orders: list[FilledOrder]) -> typing.Iterable[typing.Tuple[datetime.datetime, float]]:
    balance = account['equity']

    positions = {}

    for order in reversed(filled_orders):
        # print(order)
        symbol = order['symbol']

        value = order['filled_qty'] * order['filled_avg_price']
        value = -value if order['side'] == 'BUY' else value

        positions[symbol] = positions.get(symbol, {
            "value": 0,
            "qty": 0,
        })
        positions[symbol]['value'] -= value
        positions[symbol]['qty'] += order['filled_qty'] if order['side'] == 'BUY' else - \
            order['filled_qty']

        if positions[symbol]['qty'] == 0:
            balance += positions[symbol]['value']
            del positions[symbol]
            yield order['filled_at'], balance
        # print(order['filled_at'], round(balance, 2))
