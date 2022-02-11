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
            logging.exception(
                f"HTTP {e.response.status_code} {e.response.text}")
        except Exception as e:
            logging.exception(f"Unexpected Exception")
    logging.info("Loop is finished.")


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
    logging.info(f"{stage_time} {cash=}")

    position = get_current_position(symbol)
    logging.info(
        f"{stage_time} position={json.dumps(position, sort_keys=True, indent=2)}")

    # 2. at each minute, gather new candle's data

    wait_until(trade_time)

    # Get price action data
    candles = get_candles(  # NOTE: all values are unadjusted
        symbol, "1", (trade_time - timedelta(days=4)).date(), trade_time.date())
    rsi = get_rsi(candles)
    williamsr = get_williamsr(candles)

    # Logic
    rsi_buy_lt_threshold = 40
    williamsr_buy_lt_threshold = -70
    buy_reason = rsi < rsi_buy_lt_threshold and williamsr < williamsr_buy_lt_threshold

    rsi_sell_gt_threshold = 70
    williamsr_sell_gt_threshold = -30
    sell_reason = rsi > rsi_sell_gt_threshold and williamsr > williamsr_sell_gt_threshold

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
        # TODO: sizing configuration
        # symbol current values
        "last_candle": candles[-1],
        "rsi": rsi,
        "williamsr": williamsr,
        # strategy configuration
        "rsi_buy_lt_threshold": rsi_buy_lt_threshold,
        "williamsr_buy_lt_threshold": williamsr_buy_lt_threshold,
        "rsi_sell_gt_threshold": rsi_sell_gt_threshold,
        "williamsr_sell_gt_threshold": williamsr_sell_gt_threshold,
    }

    # Execute strategy

    # backtesting found usually 4 buys per 2-day period
    equity_percentage = 0.2  # TODO: 5 shares... maybe means 5 times?

    if not position and buy_reason:
        latest_price = candles[-1]["close"]
        target_quantity = size_buy(
            account,
            equity_percentage,
            # TODO: when switch to limit order, remove 1% slippage buffer
            asset_price=latest_price * 1.01,
            at_most_shares=5,  # TODO: 5 shares... maybe means at most 5 shares?
            # so we buy at least 1 share in small accounts
            at_least_shares=1)
        # TODO: support premarket, aftermarket
        logging.info(f"buying, {rsi=:.1f} {williamsr=:.1f} {target_quantity=}")

        intention["side"] = "buy"
        intention["quantity"] = target_quantity
        log_intentions("minion", [intention], metadata)

        buy_symbol_market(symbol, target_quantity)

    elif position and sell_reason:
        position_quantity = float(position["qty"])
        logging.info(
            f"selling, {rsi=:.1f} {williamsr=:.1f} {position_quantity=}")

        intention["side"] = "sell"
        intention["quantity"] = position_quantity
        log_intentions("minion", [intention], metadata)

        sell_symbol_market(symbol, position_quantity)

    else:
        logging.info(f"no action, {rsi=:.1f} {williamsr=:.1f}")


def main():
    symbol = "NRGU"
    logging.info(f"Starting {symbol} live trading")
    loop(symbol)


if __name__ == "__main__":
    main()
