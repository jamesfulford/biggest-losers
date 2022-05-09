
from datetime import date, timedelta
import datetime
from src.backtest.brackets_historical import Bracket, backtest_brackets
from src.trading_day import generate_trading_days, get_market_close_on_day, get_market_open_on_day, is_during_market_hours
from src.data.polygon.get_candles import get_candles


def open_bracket_close(day: date):
    market_today = day
    candles = get_candles("NRGU", "1", market_today, market_today)
    if not candles:
        return
    candles = list(
        filter(lambda c: is_during_market_hours(c["datetime"]), candles))

    # knob: try exiting at different times instead of at close
    candles = list(
        filter(lambda c: (c["datetime"].hour, c["datetime"].minute) < (11, 30), candles))

    market_open = get_market_open_on_day(market_today)
    market_close = get_market_close_on_day(market_today)
    # TODO: try buying more intraday
    brackets: list[Bracket] = [
        {
            "take_profit_percentage": 0.02,
            "stop_loss_percentage": 0.25,  # unusually low please
            "until": datetime.time(10, 30),
        },
        {
            "take_profit_percentage": 0.02,
            "stop_loss_percentage": 0.005,
            "until": datetime.time(15, 59),
        },
    ]

    # buy at open
    buy_price = candles[0]["open"]

    # place brackets
    sell_price, last_candle, _last_bracket = backtest_brackets(
        candles, brackets, buy_price)

    # when brackets/candles end, sell
    if not sell_price:
        sell_price = last_candle["close"]

    roi = (sell_price - buy_price) / buy_price
    return roi


def main():
    rois = []
    balance = 1
    for day in generate_trading_days(date(2021, 1, 1), date(2021, 12, 31)):
        # TODO: try setting stops/limits based on rolling average of past trades?
        roi = open_bracket_close(day)
        if not roi:
            continue
        rois.append(roi)

        # geometric
        balance *= 1 + roi
        g_roi = (balance ** (1 / len(rois))) - 1

        # arithmetic
        period = 20
        a_roi_sma = sum(rois[-period:]) / len(rois[-period:])

        # daily win rate
        win_rate = len(list(filter(lambda r: r > 0, rois))) / len(rois)

        print(
            f"{day} ROI {period}SMA: {a_roi_sma:.1%} ({len(rois)}) YTD {balance:.1f}x (geometric roi: {g_roi:.1%}) ({win_rate:.1%})".ljust(80), "=" * int(a_roi_sma / .002))
