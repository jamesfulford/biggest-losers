from datetime import datetime, timedelta, date
import logging
from typing import Optional, cast
from zoneinfo import ZoneInfo

#
# date logic
#

# TODO: holidays (usually handled elsewhere dynamically), days to skip (also usually handled elsewhere)


def next_trading_day(day: date) -> date:
    while day <= date.today() + timedelta(
        days=100
    ):  # instead of infinite loop, give None
        day = day + timedelta(days=1)
        if day.weekday() < 5:
            return day

    raise ValueError(f"next_trading_day: {day=} is too far in the future")


def previous_trading_day(day: date) -> date:
    while day >= date(2000, 1, 1):  # instead of infinite loop, give None
        day = day - timedelta(days=1)
        if day.weekday() < 5:
            return day

    raise ValueError(f"previous_trading_day: {day=} is too far in the past")


def today_or_next_trading_day(d: date):
    """
    Sat, Sun -> Monday, else no-op
    """
    return next_trading_day(previous_trading_day(d))


def today_or_previous_trading_day(d: date):
    """
    Sat, Sun -> Friday, else no-op
    """
    return previous_trading_day(next_trading_day(d))


def generate_trading_days(start: date, end: date):
    day = next_trading_day(previous_trading_day(start))
    while day <= end:
        yield day
        day = next_trading_day(day)


#
# datetime logic
#

# TODO: half-days (like Black Friday)

MARKET_TIMEZONE = ZoneInfo("America/New_York")


def now(d: Optional[datetime] = None) -> datetime:
    if d is None:
        d = datetime.now()
    return d.astimezone(MARKET_TIMEZONE)


def today(d: Optional[datetime] = None) -> date:
    if d is None:
        d = datetime.now()
    return now(d).date()


def get_market_open_on_day(d: date) -> Optional[datetime]:
    if d.weekday() >= 5:
        return None
    return datetime(d.year, d.month, d.day, 9, 30, 0, 0, MARKET_TIMEZONE)


def get_market_close_on_day(d: date) -> Optional[datetime]:
    if d.weekday() >= 5:
        return None
    return datetime(d.year, d.month, d.day, 16, 0, 0, 0, MARKET_TIMEZONE)


def get_last_market_open(d: datetime) -> datetime:
    d = now(d)

    today_open = get_market_open_on_day(d.date())
    if (
        not today_open or today_open > d
    ):  # weekend, or today's open has not happened yet
        # open of previous trading day
        return cast(datetime, get_market_open_on_day(previous_trading_day(d.date())))
    else:
        return today_open


def get_last_market_close(d: datetime) -> datetime:
    d = now(d)

    today_close = get_market_close_on_day(d.date())
    if (
        not today_close or today_close > d
    ):  # weekend, or today's close has not happened yet
        # close of previous trading day
        return cast(datetime, get_market_close_on_day(previous_trading_day(d.date())))
    else:
        return today_close


def is_during_market_hours(d: datetime) -> bool:
    d = now(d)
    last_open = get_last_market_open(d)
    last_close = get_last_market_close(d)

    # weekend
    if not last_open or not last_close:
        return False

    # trick: during market hours, last close is the previous day but last open is current day
    # so if last open comes later than last close, then we're in market hours
    return last_open > last_close


if __name__ == "__main__":
    t = today()

    #
    # test date logic
    #
    friday = date(2021, 12, 31)
    saturday = date(2022, 1, 1)
    sunday = date(2022, 1, 2)
    monday = date(2022, 1, 3)
    tuesday = date(2022, 1, 4)

    assert next_trading_day(monday) == tuesday
    assert next_trading_day(friday) == monday

    assert previous_trading_day(tuesday) == monday
    assert previous_trading_day(monday) == friday

    assert today_or_next_trading_day(friday) == friday
    assert today_or_next_trading_day(saturday) == monday
    assert today_or_next_trading_day(sunday) == monday
    assert today_or_next_trading_day(monday) == monday

    assert today_or_previous_trading_day(friday) == friday
    assert today_or_previous_trading_day(saturday) == friday
    assert today_or_previous_trading_day(sunday) == friday
    assert today_or_previous_trading_day(monday) == monday

    #
    # test datetime logic
    #

    friday_premarket = datetime(2021, 12, 31, 9, 0, 0, 0, MARKET_TIMEZONE)
    friday_open = datetime(2021, 12, 31, 9, 30, 0, 0, MARKET_TIMEZONE)
    friday_during = datetime(2021, 12, 31, 10, 0, 0, 0, MARKET_TIMEZONE)
    friday_close = datetime(2021, 12, 31, 16, 0, 0, 0, MARKET_TIMEZONE)
    friday_after = datetime(2021, 12, 31, 17, 0, 0, 0, MARKET_TIMEZONE)

    sunday = datetime(2022, 1, 1, 13, 0, 0, 0, MARKET_TIMEZONE)
    saturday = datetime(2022, 1, 2, 13, 0, 0, 0, MARKET_TIMEZONE)

    monday_premarket = datetime(2022, 1, 3, 9, 0, 0, 0, MARKET_TIMEZONE)
    monday_open = datetime(2022, 1, 3, 9, 30, 0, 0, MARKET_TIMEZONE)
    monday_close = datetime(2022, 1, 3, 16, 0, 0, 0, MARKET_TIMEZONE)
    monday_after = datetime(2022, 1, 3, 17, 0, 0, 0, MARKET_TIMEZONE)

    tuesday_premarket = datetime(2022, 1, 4, 9, 0, 0, 0, MARKET_TIMEZONE)
    tuesday_open = datetime(2022, 1, 4, 9, 30, 0, 0, MARKET_TIMEZONE)
    tuesday_close = datetime(2022, 1, 4, 16, 0, 0, 0, MARKET_TIMEZONE)

    assert get_last_market_open(friday_during) == friday_open
    assert get_last_market_open(friday_close) == friday_open
    assert get_last_market_open(friday_after) == friday_open
    assert get_last_market_open(saturday) == friday_open
    assert get_last_market_open(sunday) == friday_open
    assert get_last_market_open(monday_premarket) == friday_open
    assert get_last_market_open(monday_close) == monday_open
    assert get_last_market_open(tuesday_premarket) == monday_open

    assert get_last_market_close(friday_after) == friday_close
    assert get_last_market_close(saturday) == friday_close
    assert get_last_market_close(sunday) == friday_close
    assert get_last_market_close(monday_premarket) == friday_close
    assert get_last_market_close(monday_open) == friday_close
    assert get_last_market_close(monday_after) == monday_close
    assert get_last_market_close(tuesday_premarket) == monday_close
