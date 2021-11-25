from datetime import timedelta
from datetime import date
import os
from requests.models import HTTPError

from grouped_aggs import enrich_grouped_aggs, fetch_grouped_aggs_with_cache

API_KEY = os.environ['POLYGON_API_KEY']
HOME = os.environ['HOME']


def next_trading_day(day):
    while True:
        day = day + timedelta(days=1)
        if day.weekday() < 5:
            return day


def fetch_biggest_losers(day, end_date):
    previous_day_grouped_aggs = None
    previous_day_biggest_losers = []
    total_losers = []

    while day < end_date:
        previous_day = day
        day = next_trading_day(day)

        try:
            raw_grouped_aggs = fetch_grouped_aggs_with_cache(day)
        except HTTPError as e:
            if e.response.status_code == 403:
                print(e, e.response.json())
                continue
            raise e

        # skip days where API returns no data (like trading holiday)
        if 'results' not in raw_grouped_aggs:
            print(f'no results for {day}, might have been a trading holiday')
            continue
        grouped_aggs = enrich_grouped_aggs(raw_grouped_aggs)

        if not previous_day_grouped_aggs:
            previous_day_grouped_aggs = grouped_aggs
            continue

        #
        # sell biggest losers
        #

        # for each of yesterday's biggest losers (if they are trading today)
        for loser_yesterday in filter(lambda t: t["T"] in grouped_aggs['tickermap'], previous_day_biggest_losers):
            loser_today = grouped_aggs['tickermap'][loser_yesterday["T"]]

            spy_day_before = previous_day_grouped_aggs["tickermap"]["SPY"]
            spy_day_of_loss = grouped_aggs["tickermap"]["SPY"]

            total_losers.append({
                "day_of_loss": previous_day,
                "day_after": day,
                "loser_day_of_loss": loser_yesterday,
                "loser_day_after": loser_today,
                "spy_day_of_loss_percent_change": (spy_day_of_loss['c'] - spy_day_before['c']) / spy_day_before['c'],
                "spy_day_of_loss_intraday_percent_change": (spy_day_of_loss['c'] - spy_day_of_loss['o']) / spy_day_of_loss['o'],
            })

        #
        # go find biggest losers for the next day
        #

        # skip if wasn't present yesterday
        tickers_also_present_yesterday = list(filter(
            lambda t: t['T'] in previous_day_grouped_aggs['tickermap'], grouped_aggs['results']))

        for ticker in tickers_also_present_yesterday:
            previous_day_ticker = previous_day_grouped_aggs['tickermap'][ticker['T']]

            ticker['percent_change'] = (
                ticker['c'] - previous_day_ticker['c']) / previous_day_ticker['c']

        previous_day_biggest_losers = sorted(tickers_also_present_yesterday,
                                             key=lambda t: t['percent_change'])[:20]

        for loser in previous_day_biggest_losers:
            loser['rank'] = previous_day_biggest_losers.index(loser) + 1

        #
        # advance to next day
        #
        previous_day_grouped_aggs = grouped_aggs

    return total_losers


# keep in sync with usage of write_csv
biggest_losers_csv_headers = [
    "day_of_loss",
    "day_of_loss_weekday",
    "day_of_loss_month",
    "day_after",
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
    "overnight_strategy_is_win_bool",
]


def prepare_biggest_losers_csv(path):
    try:
        os.remove(path)
    except:
        pass

    def write_to_csv(line):
        with open(path, "a") as f:
            f.write(line + "\n")
    write_to_csv(",".join(biggest_losers_csv_headers))

    start_date = date(2019, 11, 18)
    start_date = date(2021, 11, 18)
    end_date = date.today()

    biggest_losers = fetch_biggest_losers(start_date, end_date)

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
            overnight_strategy_roi > 0,
        ]))))


def main():
    path = f"{HOME}/biggest_losers.csv"
    prepare_biggest_losers_csv(path)


if __name__ == "__main__":
    main()
