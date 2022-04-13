
from datetime import datetime, date
from typing import TypedDict


class Candle(TypedDict):
    open: float
    high: float
    low: float
    close: float
    volume: int


class CandleIntraday(Candle):
    datetime: datetime


class CandleInterday(Candle):
    date: date
