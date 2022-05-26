import datetime
import typing
from src.data.types.candles import CandleInterday, CandleIntraday, Candle

import abc


class Exiter(abc.ABC):

    def prime(self, candle: Candle) -> None:
        """
        Called on entry candle, before observe.
        """
        raise NotImplementedError()

    def observe(self, candle: Candle) -> typing.Optional[float]:
        """
        If a value is returned, that is the price assumed to be the exit price.
        May be stateful. Implementors should be sure to behave sensibly if called after indicating an exit.
        """
        raise NotImplementedError()


class StopLossFixedPriceExiter(Exiter):
    def __init__(self, stop_loss_price: float):
        self.stop_loss_price = stop_loss_price

    def prime(self, candle: Candle) -> None:
        pass

    def observe(self, candle: Candle) -> typing.Optional[float]:
        if candle["low"] < self.stop_loss_price:
            return self.stop_loss_price
        return None


class TakeProfitFixedPriceExiter(Exiter):
    def __init__(self, take_profit_price: float):
        self.take_profit_price = take_profit_price

    def prime(self, candle: Candle) -> None:
        pass

    def observe(self, candle: Candle) -> typing.Optional[float]:
        if candle["high"] > self.take_profit_price:
            return self.take_profit_price
        return None


class StopLossTrailingFixedOffsetExiter(Exiter):
    def __init__(self, fixed_offset: float):
        self.high_mark: typing.Optional[float] = None
        self.fixed_offset: float = fixed_offset

    def prime(self, candle: Candle) -> None:
        self.high_mark = max(
            self.high_mark, candle['high']) if self.high_mark is not None else candle['high']

    def observe(self, candle: Candle) -> typing.Optional[float]:
        self.high_mark = max(
            self.high_mark, candle['high']) if self.high_mark is not None else candle['high']

        if candle['low'] < self.high_mark - self.fixed_offset:
            return self.high_mark - self.fixed_offset


class StopLossTrailingPercentageExiter(Exiter):
    def __init__(self, percentage: float):
        """
        If mark goes below percentage of highest mark observed, exit.
        ex: with percentage of 0.05 (5%), if entered at 90 and a high of 100, will exit at 95.
        """
        self.high_mark: typing.Optional[float] = None
        self.percentage: float = percentage

    def prime(self, candle: Candle) -> None:
        self.high_mark = max(
            self.high_mark, candle['high']) if self.high_mark is not None else candle['high']

    def observe(self, candle: Candle) -> typing.Optional[float]:
        self.high_mark = max(
            self.high_mark, candle['high']) if self.high_mark is not None else candle['high']

        if candle['low'] < self.high_mark * (1-self.percentage):
            return self.high_mark * (1-self.percentage)


class TakeProfitLeadingFixedOffsetExiter(Exiter):
    def __init__(self, fixed_offset: float):
        self.low_mark: typing.Optional[float] = None
        self.fixed_offset: float = fixed_offset

    def prime(self, candle: Candle) -> None:
        self.low_mark = min(
            self.low_mark, candle['low']) if self.low_mark is not None else candle['low']

    def observe(self, candle: Candle) -> typing.Optional[float]:
        self.low_mark = min(
            self.low_mark, candle['low']) if self.low_mark is not None else candle['low']

        if candle['high'] > self.low_mark + self.fixed_offset:
            return self.low_mark + self.fixed_offset


class TakeProfitLeadingPercentageExiter(Exiter):
    def __init__(self, percentage: float):
        self.low_mark: typing.Optional[float] = None
        self.percentage: float = percentage

    def prime(self, candle: Candle) -> None:
        self.low_mark = min(
            self.low_mark, candle['low']) if self.low_mark is not None else candle['low']

    def observe(self, candle: Candle) -> typing.Optional[float]:
        self.low_mark = min(
            self.low_mark, candle['low']) if self.low_mark is not None else candle['low']

        if candle['high'] > self.low_mark * (1+self.percentage):
            return self.low_mark * (1+self.percentage)


class TimeboxedExiter(Exiter):
    def __init__(self, target_exit: datetime.datetime):
        """
        Exits on open of candle with target datetime or later.
        """
        self.target_exit = target_exit

    def prime(self, candle: Candle) -> None:
        pass

    def observe(self, _candle: Candle) -> typing.Optional[float]:
        if 'datetime' in _candle:
            candle = typing.cast(CandleIntraday, _candle)
            if candle['datetime'] >= self.target_exit:
                return candle['open']
        else:
            candle = typing.cast(CandleInterday, _candle)
            if candle['date'] >= self.target_exit.date():
                return candle['open']

#
# Composing Exiters
#


class ComposedExiter(Exiter):
    def __init__(self, *exiters: Exiter):
        """
        Evaluates exiters in order, exiting with the price of the first to signal an exit.
        """
        self.exiters = exiters

    def prime(self, candle: Candle) -> None:
        for exiter in self.exiters:
            exiter.prime(candle)

    def observe(self, candle: Candle) -> typing.Optional[float]:
        for exiter in self.exiters:
            exit_price = exiter.observe(candle)
            if exit_price is not None:
                return exit_price
