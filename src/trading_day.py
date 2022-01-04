from datetime import timedelta, date


def next_trading_day(day: date):
    while day <= date.today():  # instead of infinite loop, give None
        day = day + timedelta(days=1)
        if day.weekday() < 5:
            return day


def previous_trading_day(day: date):
    while day >= date(2000, 1, 1):  # instead of infinite loop, give None
        day = day - timedelta(days=1)
        if day.weekday() < 5:
            return day
