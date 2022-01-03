from datetime import date

from src.grouped_aggs import get_today_grouped_aggs
from src.trading_day import next_trading_day


# TODO: rename file to `overnights.py`


def overnights(start: date, end: date):
    """
    Yields all (previous_day, day) trading day pairs entirely contained in `start` to `end` range (inclusive).
    """
    day = start
    # if `start` is a holiday, skip it
    while True:
        if get_today_grouped_aggs(start):
            break
        day = next_trading_day(day)

    previous_day = day
    day = next_trading_day(day)

    while day <= end:
        grouped_aggs = get_today_grouped_aggs(day)
        if not grouped_aggs:
            print(f'no results for {day}, might have been a trading holiday')

            # don't progress previous_day
            day = next_trading_day(day)
            continue

        yield previous_day, day

        previous_day = day
        day = next_trading_day(day)


def collect_overnights(start_date: date, end_date: date, get_actions_on_day: callable):
    previous_day_movers = []

    for previous_day, day in overnights(start_date, end_date):
        grouped_aggs = get_today_grouped_aggs(day)

        # evaluate biggest winners from 4pm previous_day (compared to close of day before that)
        # for each of yesterday's biggest winners (if they are trading today)
        for mover_yesterday in filter(lambda t: t["T"] in grouped_aggs['tickermap'], previous_day_movers):
            mover_today = grouped_aggs['tickermap'][mover_yesterday["T"]]

            yield {
                "day_of_action": previous_day,
                "day_after": day,
                "mover_day_of_action": mover_yesterday,
                "mover_day_after": mover_today,
            }

        # go find today's biggest winners
        previous_day_movers = get_actions_on_day(day)
