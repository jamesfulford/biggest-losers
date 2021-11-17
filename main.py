from datetime import datetime, timedelta
from datetime import date
import json
import os
import time
import requests

API_KEY = os.environ['POLYGON_API_KEY']
HOME = os.environ['HOME']


def read_json_cache(key):
    path = f"{HOME}/data/{key}"
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def write_json_cache(key, value):
    path = f"{HOME}/data/{key}"
    with open(path, 'w') as f:
        json.dump(value, f)


def delete_json_cache(key):
    path = f"{HOME}/data/{key}"
    try:
        os.remove(path)
    except Exception:
        pass


def fetch_grouped_aggs_with_cache(day):

    strftime = day.strftime("%Y-%m-%d")

    # cache intraday values separately
    key = f"grouped_aggs_{strftime}"
    if day == date.today() and datetime.now().hour < 16:
        key = f"grouped_aggs_{strftime}.intraday"

    cached = read_json_cache(key)
    if cached:
        # print(f'cache hit of grouped aggs for {strftime}')
        return cached

    data = fetch_grouped_aggs(day)

    write_json_cache(key, data)
    return data


def fetch_grouped_aggs(day):
    strftime = day.strftime("%Y-%m-%d")
    print(f'fetching grouped aggs for {strftime}')

    while True:
        response = requests.get(
            f'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{strftime}?adjusted=true&apiKey={API_KEY}')
        if response.status_code == 429:
            print("Rate limit exceeded, waiting...")
            time.sleep(10)
            continue
        response.raise_for_status()

        data = response.json()
        return data


def enrich_grouped_aggs(grouped_aggs):
    grouped_aggs['tickermap'] = {}
    for ticker in grouped_aggs['results']:
        grouped_aggs['tickermap'][ticker['T']] = ticker
    return grouped_aggs


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

        raw_grouped_aggs = fetch_grouped_aggs_with_cache(day)
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

    start_date = date(2021, 1, 1)
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

        # keep in sync with headers
        write_to_csv(",".join(list(map(str, [
            day_of_loss.strftime("%Y-%m-%d"),
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
        ]))))


def main():
    path = f"{HOME}/biggest_losers.csv"
    prepare_biggest_losers_csv(path)
    # from analyze import analyze_biggest_losers_csv
    # analyze_biggest_losers_csv(path)


if __name__ == "__main__":
    main()
