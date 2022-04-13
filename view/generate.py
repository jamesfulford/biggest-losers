
from datetime import date, time, timedelta
import json
from typing import cast
from src.data.finnhub.aggregate_candles import aggregate_intraday_candles, filter_candles_during_market_hours

from src.data.finnhub.finnhub import get_1m_candles, get_d_candles
from src.indicators.drawing_lines_logic import get_james_lines
from src.trading_day import now, today
from src.wait import get_next_minute_mark, wait_until


def should_continue():
    return now().time() < time(16, 0)


def main():
    symbol = 'AAPL'
    while should_continue():
        update(symbol)
        next_min = get_next_minute_mark(now())
        wait_until(next_min)


def update(symbol):
    day = today()
    candles_1m = get_1m_candles(symbol, day - timedelta(days=7), day)
    if not candles_1m:
        return
    candles_1m = filter_candles_during_market_hours(candles_1m)
    candles_5m = aggregate_intraday_candles(candles_1m, minute_candles=5)

    candles_d = get_d_candles(
        symbol, day - timedelta(days=180), day - timedelta(days=1))
    if not candles_d:
        return

    lines = get_james_lines(candles_1m=candles_1m, candles_d=candles_d)

    json.dump({
        "candles": [
            {
                "open": c['open'],
                "high": c['high'],
                "low": c['low'],
                "close": c['close'],
                # "volume": c['volume'],
                # Not true timestamp, adjusted so UI looks like America/New_York
                "time": (c['datetime'] + cast(timedelta, c['datetime'].utcoffset())).timestamp(),
                # .timestamp(),
                # "value": c['close'],
            } for c in candles_5m
        ],
        "lines": [
            {
                "title": l['source'],
                "price": l["value"],
                "color": '#2962ff' if l['state'] == 'active' else '#00bcd4',
                "lineWidth": 2 if l['state'] == 'active' else .5,
                "lineStyle": "solid" if l['state'] == 'active' else 'dashed',
                "axisLabelVisible": l['state'] == 'active',
            } for l in lines
        ]
    }, open('./view/chart.json', 'w'))
    print("done")
