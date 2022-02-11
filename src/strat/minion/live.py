# `brew install ta-lib`, then `pip3 install TA-Lib`
# To read ta-lib docs for a function (to see parameters like windows/timeperiods), do:
#   >>> from talib import RSI; print(RSI.__doc__)
from src.sizing import size_buy
import json
from datetime import datetime, timedelta, time
import logging

import numpy as np
from talib.abstract import RSI, WILLR
from requests.exceptions import HTTPError
from src.intention import log_intentions

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


def get_rsi(candles, timeperiod=14):
    inputs = {
        "open": np.array(list(map(lambda c: float(c["open"]), candles))),
        "high": np.array(list(map(lambda c: float(c["high"]), candles))),
        "low": np.array(list(map(lambda c: float(c["low"]), candles))),
        "close": np.array(list(map(lambda c: float(c["close"]), candles))),
        "volume": np.array(list(map(lambda c: float(c["volume"]), candles))),
    }
    values = RSI(inputs, timeperiod=timeperiod)
    value = float(values[-1])
    return value


def get_williamsr(candles, timeperiod=20):
    inputs = {
        "open": np.array(list(map(lambda c: float(c["open"]), candles))),
        "high": np.array(list(map(lambda c: float(c["high"]), candles))),
        "low": np.array(list(map(lambda c: float(c["low"]), candles))),
        "close": np.array(list(map(lambda c: float(c["close"]), candles))),
        "volume": np.array(list(map(lambda c: float(c["volume"]), candles))),
    }
    values = WILLR(inputs, timeperiod=timeperiod)
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
            logging.exception(
                f"HTTP {e.response.status_code} {e.response.text}")
        except Exception as e:
            logging.exception(f"Unexpected Exception")
    logging.info("Loop is finished.")


def execute_phases(symbol: str):
    #
    # parameters
    #
    rsiperiod = 14
    williamsrperiod = 20
    slow_williamsrperiod = 200
    rsi_sell_bound = 70
    rsi_buy_bound = 40
    williamsr_sell_bound = -1
    williamsr_buy_bound = -80
    slow_williamsr_buy_bound = -70

    # backtesting found usually 4 buys per 2-day period, but doing 5 as advised on Feb 10, 2022
    equity_percentage = 0.2

    #
    # script
    #
    market_now = now()
    next_interval_start = next_minute_mark(market_now)

    stage_time = next_interval_start - timedelta(seconds=10)
    # wait 1s extra to ensure candle is built
    trade_time = next_interval_start + timedelta(seconds=1)

    # 1. before each interval, fetch account/position state
    wait_until(stage_time)

    account = get_account()
    cash = float(account["cash"])
    logging.info(f"{stage_time} {cash=}")

    position = get_current_position(symbol)
    logging.info(
        f"{stage_time} position={json.dumps(position, sort_keys=True, indent=2)}")

    # 2. at each minute, gather new candle's data

    wait_until(trade_time)

    # Get price action data
    candles = get_candles(  # NOTE: all values are unadjusted
        symbol, "1", (trade_time - timedelta(days=4)).date(), trade_time.date())
    rsi = get_rsi(candles, timeperiod=rsiperiod)
    williamsr = get_williamsr(candles, timeperiod=williamsrperiod)
    slow_williamsr = get_williamsr(candles, timeperiod=slow_williamsrperiod)

    latest_price = candles[-1]["close"]

    # Logic
    should_buy = rsi < rsi_buy_bound and williamsr < williamsr_buy_bound and slow_williamsr > slow_williamsr_buy_bound
    should_sell = rsi > rsi_sell_bound and williamsr > williamsr_sell_bound

    # Logging intentions
    intention = {
        "datetime": now(),
        "symbol": symbol,
        "price": latest_price,
    }
    metadata = {
        # account state
        "cash": cash,
        "account": account,
        "position": position,
        # symbol current values
        "last_candle": candles[-1],
        "rsi": rsi,
        "williamsr": williamsr,
        "slow_williamsr": slow_williamsr,
        # strategy configuration
        "rsi_buy_bound": rsi_buy_bound,
        "williamsr_buy_bound": williamsr_buy_bound,
        "rsi_sell_bound": rsi_sell_bound,
        "williamsr_sell_bound": williamsr_sell_bound,
        "slow_williamsr_buy_bound": slow_williamsr_buy_bound,
        # sizing configuration
        "equity_percentage": equity_percentage,
    }

    # Execute strategy

    if not position and should_buy:
        target_quantity = size_buy(
            account,
            equity_percentage,
            # TODO: when switch to limit order, remove 1% slippage buffer
            asset_price=latest_price * 1.01,
            # so we buy at least 1 share in small accounts
            at_least_shares=1)
        # TODO: support premarket, aftermarket
        logging.info(
            f"buying, {rsi=:.1f} {williamsr=:.1f} {slow_williamsr=:.1f} {target_quantity=}")

        intention["side"] = "buy"
        intention["quantity"] = target_quantity
        log_intentions("minion", [intention], metadata)

        buy_symbol_market(symbol, target_quantity)

    elif position and should_sell:
        position_quantity = float(position["qty"])
        logging.info(
            f"selling, {rsi=:.1f} {williamsr=:.1f} {slow_williamsr=:.1f} {position_quantity=}")

        intention["side"] = "sell"
        intention["quantity"] = position_quantity
        log_intentions("minion", [intention], metadata)

        sell_symbol_market(symbol, position_quantity)

    else:
        logging.info(
            f"no action, {rsi=:.1f} {williamsr=:.1f} {slow_williamsr=:.1f}")


def main():
    symbol = "NRGU"
    logging.info(f"Starting {symbol} live trading")
    loop(symbol)


if __name__ == "__main__":
    main()
