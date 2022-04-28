
from datetime import date
import typing

from src.data.types.candles import CandleIntraday


class OptionContractSpecifier(typing.TypedDict):
    underlying_ticker: str  # AAPL
    contract_type: str  # call, put
    expiration_date: date
    strike_price: float
    # all things in a 'ticker', but since ticker formats vary, we will store it in these fields


OptionCandleGetter = typing.Callable[[
    OptionContractSpecifier, str, date, date], list[CandleIntraday]]
