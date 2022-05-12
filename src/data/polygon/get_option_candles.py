from datetime import date
from typing import Optional
from src.data.polygon.get_candles import get_candles
from src.data.polygon.option_chain import format_contract_specifier_to_polygon_option_ticker
from src.data.types.candles import CandleIntraday
from src.data.types.contracts import OptionContractSpecifier


def get_option_candles(spec: OptionContractSpecifier, resolution: str, start_date: date, end_date: date) -> list[CandleIntraday]:
    ticker = format_contract_specifier_to_polygon_option_ticker(spec)
    candles = get_candles(ticker, resolution, start_date, end_date)
    if not candles:
        raise ValueError(
            f"No candles found for {spec} {start_date} {end_date}")
    return candles
