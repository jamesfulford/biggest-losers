# `brew install ta-lib`, then `pip3 install TA-Lib`
# To read ta-lib docs for a function (to see parameters like windows/timeperiods), do:
#   >>> from talib import RSI; print(RSI.__doc__)
import json
from datetime import datetime, timedelta, time
import traceback

import numpy as np
from talib.abstract import RSI, WILLR
from requests.exceptions import HTTPError

from src.trading_day import now
from src.wait import wait_until
from src.data.finnhub.finnhub import get_candles
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


#
# Differences between this and backtest
# 3. live has sizing issues with the broker because of cash settling, cannot do all-in sizing (or in small margin accounts will have PDT issues)
# 4. slippage (NRGU is fairly low volume)
def loop(symbol: str):
    while now().time() < time(16, 1):
        try:
            execute_phases(symbol)
        except HTTPError as e:
            if e.response.status_code == 403:
                print(f"{now()} HTTP 403 {e.response.text}")
            else:
                raise e
        except Exception as e:
            print(e)
            print(f"{traceback.format_exc(e)}")
    print("Loop is finished.")


def execute_phases(symbol: str):
    # TODO: consider using 5m intervals instead of 1m

    market_now = now()
    next_interval_start = next_minute_mark(market_now)

    stage_time = next_interval_start - timedelta(seconds=10)
    # wait 1s extra to ensure candle is built
    trade_time = next_interval_start + timedelta(seconds=1)

    # 1. before each interval, fetch account/position state
    wait_until(stage_time)

    account = get_account()
    cash = float(account["cash"])
    print(f"{stage_time} {cash=}")

    position = get_current_position(symbol)
    print(f"{stage_time} position={json.dumps(position, indent=2)}")

    # 2. at each minute, gather new candle's data

    wait_until(trade_time)

    # NOTE: all values are unadjusted
    candles = get_candles(
        "NRGU", "1", (trade_time - timedelta(days=4)).date(), trade_time.date())

    rsi = get_rsi(candles)
    williamsr = get_williamsr(candles)

    #
    # Sizing
    #
    target_account_usage = 0.95  # TODO: when limits implemented, this can be 1.0
    _limit_price = candles[-1]["close"]
    target_quantity = int((float(account["cash"]) *
                           target_account_usage) // _limit_price)

    #
    # Execute strategy
    #

    buy_reason = rsi < 40 and williamsr < -70
    sell_reason = rsi > 70 and williamsr > -30

    if not position and buy_reason:
        # TODO: support premarket, aftermarket
        print(f"{trade_time} buying, {rsi=:.1f} {williamsr=:.1f} {target_quantity=}")
        buy_symbol_market(symbol, target_quantity)

    elif position and sell_reason:
        position_quantity = float(position["qty"])
        print(f"{trade_time} selling, {rsi=:.1f} {williamsr=:.1f} {position_quantity=}")
        sell_symbol_market(symbol, position_quantity)

    else:
        print(f"{trade_time} no action, {rsi=:.1f} {williamsr=:.1f}")


def main():
    symbol = "NRGU"
    print(f"Starting {symbol} live trading")
    loop(symbol)


if __name__ == "__main__":
    main()
