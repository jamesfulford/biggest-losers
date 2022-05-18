import datetime
import typing
import src.types as types

import unittest


class TestTrade(unittest.TestCase):

    def test_from_orders(self):
        start = datetime.datetime.now() - datetime.timedelta(hours=7)
        orders = [

            types.FilledOrder(intention=None, symbol='AAPL', quantity=-50, price=75,
                              datetime=start + datetime.timedelta(hours=3)),  # wrong order
            types.FilledOrder(intention=None, symbol='AAPL', quantity=50, price=50,
                              datetime=start),
            types.FilledOrder(intention=None, symbol='AAPL', quantity=50, price=100,
                              datetime=start + datetime.timedelta(hours=1)),
            types.FilledOrder(intention=None, symbol='AAPL', quantity=-50, price=80,
                              datetime=start + datetime.timedelta(hours=2)),

            # TODO: should handle short positions just fine
            types.FilledOrder(intention=None, symbol='AAPL', quantity=-50, price=80,
                              datetime=start + datetime.timedelta(hours=5)),
            types.FilledOrder(intention=None, symbol='AAPL', quantity=50, price=80,
                              datetime=start + datetime.timedelta(hours=5, minutes=1)),


            types.FilledOrder(intention=None, symbol='TSLA', quantity=50, price=800,
                              datetime=start),
            types.FilledOrder(intention=None, symbol='TSLA', quantity=-50, price=900,
                              datetime=start + datetime.timedelta(hours=9)),

            # should not show up
            types.FilledOrder(intention=None, symbol='QQQ', quantity=50, price=800,
                              datetime=start),
        ]
        trades = typing.cast(list[types.Trade], list(
            types.Trade.from_orders(orders)))

        assert len(trades) == 3

        trade = trades[0]
        assert trade.get_symbol() == 'AAPL'
        assert trade.get_start() == start
        assert trade.get_end() == start + datetime.timedelta(hours=3)

        trade = trades[1]
        assert trade.get_symbol() == 'AAPL'
        assert trade.get_start() == start + datetime.timedelta(hours=5)
        assert trade.get_end() == start + datetime.timedelta(hours=5, minutes=1)
        # TODO: assert is short

        trade = trades[2]
        assert trade.get_symbol() == 'TSLA'
        assert trade.get_start() == start
        assert trade.get_end() == start + datetime.timedelta(hours=9)

    def test_flow(self):
        start = datetime.datetime.now() - datetime.timedelta(hours=7)
        orders = [
            types.FilledOrder(intention=None, symbol='AAPL', quantity=50, price=50,
                              datetime=start),
            types.FilledOrder(intention=None, symbol='AAPL', quantity=50, price=100,
                              datetime=start + datetime.timedelta(hours=1)),
            types.FilledOrder(intention=None, symbol='AAPL', quantity=-50, price=80,
                              datetime=start + datetime.timedelta(hours=2)),
            types.FilledOrder(intention=None, symbol='AAPL', quantity=-50, price=75,
                              datetime=start + datetime.timedelta(hours=3)),
        ]
        trade = typing.cast(types.Trade, next(types.Trade.from_orders(orders)))

        assert trade.get_quantity() == 100
        assert trade.get_symbol() == 'AAPL'
        assert trade.get_start() == start
        assert trade.get_end() == start + datetime.timedelta(hours=3)

        assert trade.get_average_entry_price(
        ) * trade.get_quantity() == trade.get_value_spent()
        assert trade.get_average_exit_price(
        ) * trade.get_quantity() == trade.get_value_extracted()

        assert (trade.get_average_exit_price() - trade.get_average_entry_price()
                ) * trade.get_quantity() == trade.get_profit_loss()
        assert (trade.get_value_extracted() -
                trade.get_value_spent()) == trade.get_profit_loss()


class TestTradeSummary(unittest.TestCase):
    def test_flow(self):
        start = datetime.datetime.now() - datetime.timedelta(hours=7)
        orders = [
            types.FilledOrder(intention=None, symbol='AAPL', quantity=50, price=50,
                              datetime=start),
            types.FilledOrder(intention=None, symbol='AAPL', quantity=50, price=100,
                              datetime=start + datetime.timedelta(hours=1)),
            types.FilledOrder(intention=None, symbol='AAPL', quantity=-50, price=80,
                              datetime=start + datetime.timedelta(hours=2)),
            types.FilledOrder(intention=None, symbol='AAPL', quantity=-50, price=75,
                              datetime=start + datetime.timedelta(hours=3)),
        ]
        trade = typing.cast(types.Trade, next(types.Trade.from_orders(orders)))

        trade_summary = types.TradeSummary.from_trade(trade)

        assert trade_summary.trade == trade
        assert trade_summary.quantity == trade.get_quantity()
        assert trade_summary.average_entry_price == trade.get_average_entry_price()
        assert trade_summary.average_exit_price == trade.get_average_exit_price()
        assert trade_summary.entered_at == trade.get_start()
        assert trade_summary.exited_at == trade.get_end()

        assert trade_summary.get_value_spent() == trade.get_value_spent()
        assert trade_summary.get_value_extracted() == trade.get_value_extracted()
        assert trade_summary.get_profit_loss() == trade.get_profit_loss()

        assert trade_summary.get_virtual_orders()[0] == types.FilledOrder(
            intention=None, symbol='AAPL', quantity=trade.get_quantity(), price=trade.get_average_entry_price(), datetime=trade.get_start())
        assert trade_summary.get_virtual_orders()[1] == types.FilledOrder(
            intention=None, symbol='AAPL', quantity=trade.get_quantity(), price=trade.get_average_exit_price(), datetime=trade.get_end())


class TestFilledOrder(unittest.TestCase):
    def test_find_intention(self):
        start = datetime.datetime.now()
        intentions = [
            types.Intention(datetime=start, symbol='AAPL',
                            extra={'is_cool': True}),
            types.Intention(datetime=start + datetime.timedelta(minutes=2),
                            symbol='AAPL', extra={'is_cool': True}),
            types.Intention(datetime=start + datetime.timedelta(minutes=3),
                            symbol='AAPL', extra={'is_cool': True})
        ]
        order = types.FilledOrder(intention=None, symbol='AAPL', quantity=1,
                                  price=1, datetime=start + datetime.timedelta(minutes=2))
        assert order.find_matching_intention(intentions) == intentions[1]

        assert order.find_matching_intention([]) == None

    def test_order_buy_sell_long_short_interpretation(self):
        start = datetime.datetime.now()
        order = types.FilledOrder(intention=None, symbol='AAPL', quantity=1,
                                  price=1, datetime=start + datetime.timedelta(minutes=2))

        assert order.is_buy()
        assert not order.is_sell()
        assert order.is_long()
        assert not order.is_short()

        order = types.FilledOrder(intention=None, symbol='AAPL', quantity=-1,
                                  price=1, datetime=start + datetime.timedelta(minutes=2))

        assert not order.is_buy()
        assert order.is_sell()
        assert order.is_long()
        assert not order.is_short()

        # TODO: is_short, not is_long
