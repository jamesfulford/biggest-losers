

import dataclasses
import datetime
import typing


@dataclasses.dataclass
class Intention:
    datetime: datetime.datetime
    symbol: str
    extra: dict[str, typing.Any]


@dataclasses.dataclass
class FilledOrder:
    intention: typing.Optional[Intention]

    symbol: str  # for options, follows Polygon format

    quantity: float  # sum of all legs
    # quantity is positive -> adding to position, moves position away from 0
    # quantity is negative -> removing from position, moves position closer to 0

    price: float  # average price of all legs

    datetime: datetime.datetime  # END of fulfillment period

    trade_is_long: bool = True

    def find_matching_intention(self, intentions: list[Intention]) -> typing.Optional[Intention]:
        """
        Finds intention that has same symbol as order and date before but nearest this order, if any
        """
        try:
            return max(filter(
                lambda intention: intention.symbol == self.symbol and intention.datetime <= self.datetime,
                intentions,
            ), key=lambda i: i.datetime)
        except ValueError:  # `filter` returns empty sequence
            return None

    def get_position_difference(self) -> float:
        """Will be positive when selling long."""
        return -self.quantity * self.price

    def is_buy(self) -> bool:
        return self.quantity > 0

    def is_sell(self) -> bool:
        return not self.is_buy()

    def is_long(self) -> bool:
        return self.trade_is_long

    def is_short(self) -> bool:
        return not self.is_long()


@dataclasses.dataclass
class Trade:
    orders: list[FilledOrder]  # assumed to be ordered from first to last

    @classmethod
    def from_orders(cls, orders: list[FilledOrder]) -> typing.Iterator:
        """
        Returns Trades grouped by symbol and related orders (when position quantity resets to 0)
        """
        assert not any(o.is_short()
                       for o in orders), "TODO: add support for short trades"

        def group_orders_by_trade(filled_orders: list[FilledOrder]) -> typing.Iterable[list[FilledOrder]]:
            # group by symbol
            orders_by_symbol: dict[str, list[FilledOrder]] = {}
            for order in filled_orders:  # latest last
                orders_by_symbol[order.symbol] = orders_by_symbol.get(
                    order.symbol, []) + [order]

            for grouped_orders in orders_by_symbol.values():
                orders = sorted(grouped_orders, key=lambda o: o.datetime)
                # group by orders that go from 0 to 0 position
                # NOTE: open trades are not yielded
                current_qty = 0
                index_of_last_trade = 0
                for i in range(len(orders)):
                    order = orders[i]
                    current_qty += order.quantity
                    if current_qty == 0:

                        # before : is inclusive, after : is exclusive
                        trade_orders = orders[index_of_last_trade:i + 1]
                        index_of_last_trade = i + 1

                        yield trade_orders

        for trade_orders in group_orders_by_trade(orders):
            yield Trade(orders=sorted(trade_orders, key=lambda o: o.datetime))

    def get_quantity(self) -> float:
        return sum(o.quantity for o in self.orders if o.is_buy())

    def get_start(self) -> datetime.datetime:
        return self.orders[0].datetime

    def get_end(self) -> datetime.datetime:
        return self.orders[-1].datetime

    def get_symbol(self) -> str:
        return self.orders[0].symbol

    # Calculations

    def get_value_spent(self):
        return sum(o.price * o.quantity for o in self.orders if o.is_buy())

    def get_value_extracted(self):
        return sum(o.price * -o.quantity for o in self.orders if o.is_sell())

    def get_average_entry_price(self) -> float:
        return self.get_value_spent() / self.get_quantity()

    def get_average_exit_price(self) -> float:
        return self.get_value_extracted() / self.get_quantity()

    def get_profit_loss(self):
        return sum(o.get_position_difference() for o in self.orders)

# TODO: Position, also iterator through a Trade's positions after each order
# TODO: Calculate Position's break-even point


@dataclasses.dataclass
class TradeSummary:
    trade: typing.Optional[Trade]

    entered_at: datetime.datetime
    exited_at: datetime.datetime

    average_entry_price: float
    average_exit_price: float

    quantity: float

    @classmethod
    def from_trade(cls, trade: Trade):
        return TradeSummary(trade=trade, entered_at=trade.get_start(), exited_at=trade.get_end(), average_entry_price=trade.get_average_entry_price(), average_exit_price=trade.get_average_exit_price(), quantity=trade.get_quantity())

    def get_symbol(self) -> typing.Optional[str]:
        return self.trade.get_symbol() if self.trade else ""

    def get_value_spent(self) -> float:
        return self.quantity * self.average_entry_price

    def get_value_extracted(self) -> float:
        return self.quantity * self.average_exit_price

    def get_profit_loss(self) -> float:
        return self.get_value_extracted() - self.get_value_spent()

    def get_virtual_orders(self) -> typing.Tuple[FilledOrder, FilledOrder]:
        return (
            FilledOrder(intention=None, symbol=self.get_symbol() or "", quantity=self.quantity,
                        price=self.average_entry_price, datetime=self.entered_at),
            FilledOrder(intention=None, symbol=self.get_symbol() or "", quantity=self.quantity,
                        price=self.average_exit_price, datetime=self.exited_at)
        )
