
from datetime import timedelta
from typing import Iterable
from src.data.finnhub.aggregate_candles import aggregate_intraday_candles, filter_candles_during_market_hours
from src.data.finnhub.finnhub import get_1m_candles, get_d_candles
from src.data.types.candles import CandleIntraday
from src.indicators.drawing_lines_logic import extract_james_lines
from src.trading_day import generate_trading_days, previous_trading_day, today


def progressive_1m_candles(candles: Iterable[CandleIntraday]) -> Iterable[list[CandleIntraday]]:
    simulated_candles = []
    for c in candles:
        simulated_candles.append(c)
        yield simulated_candles


def main():

    this_day = previous_trading_day(today())
    intraday_candles = get_1m_candles(
        'AAPL', this_day - timedelta(days=30), this_day)
    if not intraday_candles:
        return
    intraday_candles = filter_candles_during_market_hours(intraday_candles)

    daily_candles = get_d_candles(
        'AAPL', this_day - timedelta(days=360), this_day - timedelta(days=1))
    if not daily_candles:
        return

    for day in generate_trading_days(this_day - timedelta(days=30-7), this_day):
        all_inrange_intraday_candles = [c for c in intraday_candles if c['datetime'].date(
        ) <= day and c['datetime'].date() >= day - timedelta(days=7)]
        simulated_daily_candles = [
            c for c in daily_candles if c['date'] < day and c['date'] >= day - timedelta(days=180)]

        prior_days_intraday_candles = [
            c for c in all_inrange_intraday_candles if c['datetime'].date() < day]

        for current_day_intraday_candles in progressive_1m_candles((c for c in all_inrange_intraday_candles if c['datetime'].date() == day)):
            intraday_candle = current_day_intraday_candles[-1]
            simulated_intraday_candles = prior_days_intraday_candles + \
                current_day_intraday_candles

            simulated_intraday_candles = aggregate_intraday_candles(
                simulated_intraday_candles, minute_candles=5)[:-5]

            # TODO: switch to `get_james_lines`, so we remove some logic here
            lines = extract_james_lines(
                candles_intraday=simulated_intraday_candles, candles_d=simulated_daily_candles)

            close_price = intraday_candle['close']
            open_price = intraday_candle['open']

            lines_crossed_over = [
                line for line in lines if line['value'] > open_price and line['value'] < close_price]
            lines_crossed_under = [
                line for line in lines if line['value'] < open_price and line['value'] > close_price]

            if lines_crossed_over or lines_crossed_under:
                print(intraday_candle['datetime'], len(
                    lines_crossed_over), len(lines_crossed_under))
