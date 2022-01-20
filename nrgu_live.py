# `brew install ta-lib`, then `pip3 install TA-Lib`
# To read ta-lib docs for a function (to see parameters like windows/timeperiods), do:
#   >>> from talib import RSI; print(RSI.__doc__)
import numpy as np
from talib.abstract import RSI, WILLR
from datetime import datetime, timedelta
from src.trading_day import now
from src.wait import wait_until
from src.finnhub import get_candles

from src.broker.generic import get_positions, get_account, buy_symbol_market, sell_symbol_market


def next_minute_mark(dt: datetime) -> datetime:
    return dt - timedelta(microseconds=dt.microsecond, seconds=dt.second) + timedelta(minutes=1)


def get_current_position(symbol: str):
    """
    Returns current position {"qty", "symbol", "avg_price"} for given symbol.
    Returns `None` if no position is found.
    """
    positions = get_positions()
    return next(filter(lambda p: p["symbol"] == symbol, positions), None)


def get_rsi(candles):
    inputs = {
        "open": np.array(list(map(lambda c: float(c["open"]), candles))),
        "high": np.array(list(map(lambda c: float(c["high"]), candles))),
        "low": np.array(list(map(lambda c: float(c["low"]), candles))),
        "close": np.array(list(map(lambda c: float(c["close"]), candles))),
        "volume": np.array(list(map(lambda c: float(c["volume"]), candles))),
    }
    values = RSI(inputs, timeperiod=14)
    value = float(values[-1])
    return value


def get_williamsr(candles):
    inputs = {
        "open": np.array(list(map(lambda c: float(c["open"]), candles))),
        "high": np.array(list(map(lambda c: float(c["high"]), candles))),
        "low": np.array(list(map(lambda c: float(c["low"]), candles))),
        "close": np.array(list(map(lambda c: float(c["close"]), candles))),
        "volume": np.array(list(map(lambda c: float(c["volume"]), candles))),
    }
    values = WILLR(inputs, timeperiod=20)
    value = float(values[-1])
    return value


def loop(symbol: str):
    while True:
        # TODO: consider using 5m intervals instead of 1m
        # 1. before each interval, fetch account/position state
        market_now = now()
        next_interval_start = next_minute_mark(market_now)
        wait_until(next_interval_start - timedelta(seconds=10))

        account = get_account()
        print("account:", account)
        cash = float(account["cash"])
        print("cash:", cash)

        position = get_current_position(symbol)
        print("position:", position)

        # 2. at each minute, gather new candle's data
        wait_until(next_interval_start)
        market_now = next_interval_start

        candles = get_candles(
            "NRGU", "1", market_now.date(), market_now.date())

        rsi = get_rsi(candles)
        williamsr = get_williamsr(candles)

        #
        # Sizing
        #
        target_account_usage = 0.2
        target_quantity = (float(account["cash"]) *
                           target_account_usage) / candles[-1]["close"]

        #
        # Execute strategy
        #
        buy_reason = rsi < 30 and williamsr < -80
        sell_reason = rsi > 70 and williamsr > -20

        if not position and buy_reason:
            # TODO: support premarket, aftermarket
            print(f"buying, {rsi=} {williamsr=} {target_quantity=}")
            buy_symbol_market(symbol, target_quantity)

        elif position and sell_reason:
            print(f"selling, {rsi=} {williamsr=}")
            sell_symbol_market(symbol, position["qty"])

        else:
            print(f"no action, {rsi=} {williamsr=}")


def main():
    symbol = "NRGU"
    loop(symbol)


if __name__ == "__main__":
    main()
