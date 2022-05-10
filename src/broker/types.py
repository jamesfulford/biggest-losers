import datetime
import typing


class Order(typing.TypedDict):
    id: str
    symbol: str
    qty: float
    side: str  # BUY, SELL
    type: str  # LIMIT, MARKET, STOP, STOP_LIMIT, TRAILING_STOP
    limit_price: typing.Optional[float]
    stop_price: typing.Optional[float]
    tif: str  # DAY, GTC, IMMEDIATE_OR_CANCEL, FILL_OR_KILL
    status: str  # https://alpaca.markets/docs/trading/orders/#order-lifecycle
    submitted_at: datetime.datetime


class FilledOrder(Order):
    filled_at: datetime.datetime
    filled_qty: float
    filled_avg_price: float


class Account(typing.TypedDict):
    id: str
    type: str  # CASH | MARGIN
    cash: float
    equity: float
    long_market_value: float
    unsettled_cash: typing.Optional[float]


class Position(typing.TypedDict):
    symbol: str
    qty: float
    avg_price: float
