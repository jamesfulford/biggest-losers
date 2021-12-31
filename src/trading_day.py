from datetime import timedelta, date


def next_trading_day(day: date):
    while True:
        day = day + timedelta(days=1)
        if day.weekday() < 5:
            return day


def previous_trading_day(day: date):
    while True:
        day = day - timedelta(days=1)
        if day.weekday() < 5:
            return day
