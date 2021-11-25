from datetime import date
import os
from requests.models import HTTPError

from grouped_aggs import get_last_2_candles, get_last_n_candles, get_last_trading_day_grouped_aggs, get_today_grouped_aggs
from indicators import ema_of
from losers import get_biggest_losers
from trading_day import next_trading_day, previous_trading_day

API_KEY = os.environ['POLYGON_API_KEY']
HOME = os.environ['HOME']


def overnights(start_date, end_date):
    day = start_date
    # scroll until we can query last trading day
    while True:
        try:
            get_last_trading_day_grouped_aggs(day)
            break
        except HTTPError as e:
            if e.response.status_code == 403:
                print(e, e.response.json())
                day = next_trading_day(day)
                continue
            raise e

    # TODO: I might be losing a day in here

    previous_day = day
    day = next_trading_day(day)

    while day <= end_date:
        grouped_aggs = get_today_grouped_aggs(day)
        if not grouped_aggs:
            print(f'no results for {day}, might have been a trading holiday')

            # don't progress previous_day
            day = next_trading_day(day)
            continue

        yield previous_day, day

        previous_day = day
        day = next_trading_day(day)


def get_all_biggest_losers_with_day_after(start_date, end_date):
    previous_day_biggest_losers = []
    total_losers = []

    for previous_day, day in overnights(start_date, end_date):
        grouped_aggs = get_today_grouped_aggs(day)

        # evaluate biggest losers from 4pm previous_day (compared to close of day before that)
        # for each of yesterday's biggest losers (if they are trading today)
        for loser_yesterday in filter(lambda t: t["T"] in grouped_aggs['tickermap'], previous_day_biggest_losers):
            loser_today = grouped_aggs['tickermap'][loser_yesterday["T"]]

            loser = {
                "day_of_loss": previous_day,
                "day_after": day,
                "loser_day_of_loss": loser_yesterday,
                "loser_day_after": loser_today,
            }
            loser = enrich_loser(loser)
            total_losers.append(loser)

        # go find today's biggest losers
        previous_day_biggest_losers = get_biggest_losers(day, top_n=20)

    return total_losers


def enrich_loser(loser):
    ticker = loser["loser_day_of_loss"]["T"]
    day_of_loss = loser["day_of_loss"]

    #
    # spy action
    #
    spy_day_of_loss, spy_day_before = get_last_2_candles(day_of_loss, "SPY")

    loser["spy_day_of_loss_percent_change"] = (
        spy_day_of_loss['c'] - spy_day_before['c']) / spy_day_before['c']
    loser["spy_day_of_loss_intraday_percent_change"] = (
        spy_day_of_loss['c'] - spy_day_of_loss['o']) / spy_day_of_loss['o']

    # 100ema
    enrich_with_ema(loser, n=100)
    enrich_with_ema(loser, n=50)
    #
    # ADX
    #
    enrich_loser_with_adx(loser)

    #
    # SPO
    #

    return loser


def enrich_with_ema(loser, n, field='c'):
    ticker = loser["loser_day_of_loss"]["T"]
    day_of_loss = loser["day_of_loss"]
    candles = get_last_n_candles(day_of_loss, ticker, n=n)
    if not candles:
        return
    emas = ema_of(list(map(lambda c: c[field], reversed(candles))))

    loser[f"{n}ema"] = emas[0]


def enrich_loser_with_adx(loser):
    ticker = loser["loser_day_of_loss"]["T"]
    day_of_loss = loser["day_of_loss"]

    last_14_candles = get_last_n_candles(day_of_loss, ticker, n=14)
    if not last_14_candles:
        return


# keep in sync with usage of write_csv
biggest_losers_csv_headers = [
    "day_of_loss",
    "day_of_loss_weekday",
    "day_of_loss_month",
    "day_after",
    "days_overnight",
    "overnight_has_holiday_bool",
    "ticker",
    #
    "open_day_of_loss",
    "high_day_of_loss",
    "low_day_of_loss",
    "close_day_of_loss",
    "volume_day_of_loss",
    #
    "close_to_close_percent_change_day_of_loss",
    "intraday_percent_change_day_of_loss",
    "rank_day_of_loss",
    #
    "50ema",
    "100ema",
    #
    "open_day_after",
    "high_day_after",
    "low_day_after",
    "close_day_after",
    "volume_day_after",
    #
    "spy_day_of_loss_percent_change",
    "spy_day_of_loss_intraday_percent_change",
    #
    "overnight_strategy_roi",
    "overnight_strategy_is_win",
]


def prepare_biggest_losers_csv(path, start_date, end_date):
    biggest_losers = get_all_biggest_losers_with_day_after(
        start_date, end_date)

    try:
        os.remove(path)
    except:
        pass

    with open(path, "a") as f:
        def write_to_csv(line):
            f.write(line + "\n")

        write_to_csv(",".join(biggest_losers_csv_headers))

        for biggest_loser in biggest_losers:
            day_of_loss = biggest_loser["day_of_loss"]
            day_after = biggest_loser["day_after"]
            loser_day_of_loss = biggest_loser["loser_day_of_loss"]
            loser_day_after = biggest_loser["loser_day_after"]
            spy_day_of_loss_percent_change = biggest_loser["spy_day_of_loss_percent_change"]
            spy_day_of_loss_intraday_percent_change = biggest_loser[
                "spy_day_of_loss_intraday_percent_change"]

            intraday_percent_change = (loser_day_of_loss['c'] -
                                       loser_day_of_loss['o']) / loser_day_of_loss['o']

            overnight_strategy_roi = (
                loser_day_after['o'] - loser_day_of_loss['c']) / loser_day_of_loss['c']

            # keep in sync with headers
            write_to_csv(",".join(list(map(str, [
                day_of_loss.strftime("%Y-%m-%d"),
                day_of_loss.weekday(),
                day_of_loss.month,
                day_after.strftime("%Y-%m-%d"),
                (day_after - day_of_loss).days,
                previous_trading_day(day_after) != day_of_loss,
                loser_day_of_loss['T'],
                # day_of_loss stats
                loser_day_of_loss['o'],
                loser_day_of_loss['h'],
                loser_day_of_loss['l'],
                loser_day_of_loss['c'],
                loser_day_of_loss['v'],
                loser_day_of_loss["percent_change"],
                intraday_percent_change,
                loser_day_of_loss.get("rank", -1),
                # day of loss indicators
                biggest_loser.get("50ema", ""),
                biggest_loser.get("100ema", ""),
                # day_after stats
                loser_day_after['o'],
                loser_day_after['h'],
                loser_day_after['l'],
                loser_day_after['c'],
                loser_day_after['v'],
                # spy
                spy_day_of_loss_percent_change,
                spy_day_of_loss_intraday_percent_change,
                # results
                overnight_strategy_roi,
                1 if overnight_strategy_roi > 0 else 0,
            ]))))


def main():
    path = f"{HOME}/biggest_losers.csv"
    # earliest date I have data for on my machine
    # start_date = date(2019, 11, 18)

    start_date = date(2021, 1, 1)
    end_date = date.today()
    prepare_biggest_losers_csv(path, start_date=start_date, end_date=end_date)


if __name__ == "__main__":
    main()
