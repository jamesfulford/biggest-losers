import datetime
import typing
import unittest

from src.backtest import exiters
from src.data.types.candles import Candle


class ExitersTest(unittest.TestCase):
    def test_StopLossFixedPriceExiter(self):
        exiter = exiters.StopLossFixedPriceExiter(90)
        exiter.prime({'low': 100, 'high': 100, 'open': 100,
                     'close': 100, 'volume': 2})

        assert exiter.observe(
            {'low': 100, 'high': 100, 'open': 100, 'close': 100, 'volume': 2}) is None
        assert exiter.observe(
            {'low': 80, 'high': 100, 'open': 100, 'close': 100, 'volume': 2}) == 90

    def test_TakeProfitFixedPriceExiter(self):
        exiter = exiters.TakeProfitFixedPriceExiter(110)
        exiter.prime({'low': 100, 'high': 100, 'open': 100,
                     'close': 100, 'volume': 2})

        assert exiter.observe(
            {'low': 100, 'high': 100, 'open': 100, 'close': 100, 'volume': 2}) is None
        assert exiter.observe(
            {'low': 80, 'high': 100, 'open': 100, 'close': 90, 'volume': 2}) is None
        assert exiter.observe(
            {'low': 80, 'high': 120, 'open': 100, 'close': 90, 'volume': 2}) == 110

    def test_StopLossTrailingFixedOffsetExiter(self):
        exiter = exiters.StopLossTrailingFixedOffsetExiter(5)
        exiter.prime({'low': 98, 'high': 98, 'open': 98,
                     'close': 98, 'volume': 2})

        assert exiter.observe(
            {'low': 98, 'high': 100, 'open': 99, 'close': 100, 'volume': 2}) is None
        assert exiter.observe(
            {'low': 99, 'high': 102, 'open': 100, 'close': 99, 'volume': 2}) is None
        assert exiter.observe(
            {'low': 92, 'high': 99, 'open': 99, 'close': 94, 'volume': 2}) == 97

    def test_StopLossTrailingPercentageExiter(self):
        exiter = exiters.StopLossTrailingPercentageExiter(0.05)
        exiter.prime({'low': 98, 'high': 98, 'open': 98,
                     'close': 98, 'volume': 2})

        assert exiter.observe(
            {'low': 98, 'high': 100, 'open': 99, 'close': 100, 'volume': 2}) is None
        assert exiter.observe(
            {'low': 99, 'high': 102, 'open': 100, 'close': 99, 'volume': 2}) is None

        expected_exit = exiter.observe(
            {'low': 92, 'high': 99, 'open': 99, 'close': 94, 'volume': 2})
        self.assertAlmostEqual(typing.cast(
            float, expected_exit), 96.9, places=1)

    def test_TakeProfitLeadingFixedOffsetExiter(self):
        exiter = exiters.TakeProfitLeadingFixedOffsetExiter(5)
        exiter.prime({'low': 98, 'high': 98, 'open': 98,
                     'close': 98, 'volume': 2})

        assert exiter.observe(
            {'low': 96, 'high': 99, 'open': 98, 'close': 95, 'volume': 2}) is None
        assert exiter.observe(
            {'low': 95, 'high': 110, 'open': 95, 'close': 99, 'volume': 2}) == 100

    def test_TakeProfitLeadingPercentageExiter(self):
        exiter = exiters.TakeProfitLeadingPercentageExiter(0.05)
        exiter.prime({'low': 102, 'high': 102, 'open': 102,
                     'close': 102, 'volume': 2})

        assert exiter.observe(
            {'low': 100, 'high': 102, 'open': 102, 'close': 100, 'volume': 2}) is None

        expected_exit = exiter.observe(
            {'low': 100, 'high': 110, 'open': 100, 'close': 107, 'volume': 2})
        self.assertAlmostEqual(typing.cast(
            float, expected_exit), 105, places=0)

    def test_TimeboxedExiter(self):
        exiter = exiters.TimeboxedExiter(
            datetime.datetime(2020, 1, 1, 11, 0, 0))
        exiter.prime(typing.cast(Candle, {'low': 100, 'high': 100, 'open': 100,
                     'close': 100, 'volume': 2, 'datetime': datetime.datetime(2020, 1, 1, 10, 30)}))

        assert exiter.observe(typing.cast(Candle, {'low': 100, 'high': 100, 'open': 100,
                              'close': 100, 'volume': 2, 'datetime': datetime.datetime(2020, 1, 1, 10, 45)})) is None

        assert exiter.observe(typing.cast(Candle, {'low': 100, 'high': 103, 'open': 101,
                              'close': 102, 'volume': 2, 'datetime': datetime.datetime(2020, 1, 1, 11)})) == 101

        exiter = exiters.TimeboxedExiter(
            datetime.datetime(2020, 1, 1, 11, 0, 0))
        exiter.prime(typing.cast(Candle, {'low': 100, 'high': 100, 'open': 100,
                     'close': 100, 'volume': 2, 'date': datetime.date(2019, 1, 1)}))

        assert exiter.observe(typing.cast(Candle, {'low': 100, 'high': 100, 'open': 100,
                              'close': 100, 'volume': 2, 'date': datetime.date(2019, 12, 1)})) is None

        assert exiter.observe(typing.cast(Candle, {'low': 100, 'high': 103, 'open': 101,
                              'close': 102, 'volume': 2, 'date': datetime.date(2020, 1, 2)})) == 101

    def test_ComposedExiter(self):
        exiter = exiters.ComposedExiter(
            exiters.StopLossFixedPriceExiter(90),
            exiters.TakeProfitFixedPriceExiter(110),
        )
        exiter.prime({'low': 100, 'high': 100, 'open': 100,
                     'close': 100, 'volume': 2})

        assert exiter.observe(
            {'low': 100, 'high': 100, 'open': 100, 'close': 100, 'volume': 2}) is None
        assert exiter.observe(
            {'low': 100, 'high': 120, 'open': 100, 'close': 102, 'volume': 2}) == 110
