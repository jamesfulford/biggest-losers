from itertools import chain


def backtest_brackets(candles: list, brackets: list, base_price: float):
    """
    Returns sell_price, candle sold on, and bracket during which close occurred
    If no sale occurred, returns None, last candle in brackets, and last bracket in candles

    Caller must handle:
    - timeframing/timeboxing (only pass candles in desired time frame)
    - position entry (pass base_price for calculating percentage limits)
    - timebox exit (if stops/limits not hit and run out of brackets/candles)
    """
    candles = chain(candles)
    brackets = chain(brackets)

    candle = next(candles)
    bracket = next(brackets)

    try:
        while True:  # will escape because of `next` calls throwing StopIteration
            if candle["datetime"] >= bracket["until"]:
                bracket = next(brackets)

            take_profit = (1 + bracket["take_profit_percentage"]) * base_price
            stop_loss = (1 - bracket["stop_loss_percentage"]) * base_price

            is_stop_loss = candle["low"] < stop_loss
            is_take_profit = candle["high"] > take_profit

            if is_stop_loss:
                return stop_loss, candle, bracket
            if is_take_profit:
                return take_profit, candle, bracket

            candle = next(candles)
    except StopIteration:
        pass

    return None, candle, bracket
