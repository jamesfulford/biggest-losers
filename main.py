from datetime import datetime, timedelta
from datetime import date
import json
import os
import time
import requests

API_KEY = os.environ['POLYGON_API_KEY']


def read_json_cache(key):
    path = f"/tmp/{key}"
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def write_json_cache(key, value):
    path = f"/tmp/{key}"
    with open(path, 'w') as f:
        json.dump(value, f)


def delete_json_cache(key):
    path = f"/tmp/{key}"
    try:
        os.remove(path)
    except Exception:
        pass


def fetch_grouped_aggs_with_cache(day):

    strftime = day.strftime("%Y-%m-%d")

    key = f"grouped_aggs_{strftime}"
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


def prepare_biggest_losers_csv():
    os.remove("/tmp/biggest_losers.csv")

    def write_to_csv(line):
        with open("/tmp/biggest_losers.csv", "a") as f:
            f.write(line + "\n")
    write_to_csv(",".join([
        "day_after",
        "loser_day",
        "ticker",
        "loser_day_open",
        "loser_day_high",
        "loser_day_low",
        "loser_day_close",
        "loser_day_volume",
        "loser_day_close_to_close_percent_change",
        "loser_day_rank",
        "day_after_open",
        "day_after_high",
        "day_after_low",
        "day_after_close",
        "day_after_volume",
    ]))

    day = date(2021, 1, 1)
    end_date = date.today()

    previous_day_grouped_aggs = None
    previous_day_biggest_losers = []

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

            write_to_csv(",".join(list(map(str, [
                day.strftime("%Y-%m-%d"),
                previous_day.strftime("%Y-%m-%d"),
                loser_yesterday['T'],
                # yesterday stats
                loser_yesterday['o'],
                loser_yesterday['h'],
                loser_yesterday['l'],
                loser_yesterday['c'],
                loser_yesterday['v'],
                loser_yesterday["percent_change"],
                loser_yesterday.get("rank", -1),
                # today stats
                loser_today['o'],
                loser_today['h'],
                loser_today['l'],
                loser_today['c'],
                loser_today['v'],
            ]))))

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


def analyze_biggest_losers_csv():
    lines = []
    with open("/tmp/biggest_losers.csv", "r") as f:
        lines.extend(f.readlines())

    headers = lines[0].strip().split(",")
    # remove newlines and header row
    lines = [l.strip() for l in lines[1:]]

    # convert to dicts
    lines = [dict(zip(headers, l.strip().split(","))) for l in lines]

    lines = [{
        "day_after": datetime.strptime(l["day_after"], "%Y-%m-%d").date(),
        "loser_day": datetime.strptime(l["loser_day"], "%Y-%m-%d").date(),
        "ticker": l["ticker"],
        "loser_day_open": float(l["loser_day_open"]),
        "loser_day_close": float(l["loser_day_close"]),
        "loser_day_high": float(l["loser_day_high"]),
        "loser_day_low": float(l["loser_day_low"]),
        "loser_day_volume": float(l["loser_day_volume"]),
        "loser_day_close_to_close_percent_change": float(l["loser_day_close_to_close_percent_change"]),
        "loser_day_rank": int(l["loser_day_rank"]),
        "day_after_open": float(l["day_after_open"]),
        "day_after_close": float(l["day_after_close"]),
        "day_after_high": float(l["day_after_high"]),
        "day_after_low": float(l["day_after_low"]),
        "day_after_volume": float(l["day_after_volume"]),
    } for l in lines]

    for l in lines:
        l["close_to_open_roi"] = (
            l["day_after_open"] - l["loser_day_close"]) / l["loser_day_close"]

    print("baseline", evaluate_results(lines))

    for volume_threshold in [10000, 100000]:
        for price_criteria_i, price_criteria in enumerate([
            lambda p: p < 1.0,
            lambda p: p < 5,
            lambda p: p < 10,
            lambda p: p < 20,
            lambda p: p > 1.0,
            lambda p: p > 5,
            lambda p: p > 10,
            lambda p: p > 20,
            lambda _: True,
        ]):
            filtered_lines = list(filter(
                lambda l: l["loser_day_volume"] > volume_threshold and price_criteria(
                    l["close_to_open_roi"]),
                lines))

            results = evaluate_results(filtered_lines)
            if results:
                print(f"volume threshold {volume_threshold} price criteria {price_criteria_i}",
                      results)


def evaluate_results(lines):
    if not lines:
        return None

    plays = len(lines)

    if plays < 10:
        return None

    total_roi = sum(list(map(lambda l: l["close_to_open_roi"], lines)))

    average_roi = total_roi / plays
    win_rate = sum(
        list(map(lambda l: 1 if l["close_to_open_roi"] > 0 else 0, lines))) / plays

    return {"roi": total_roi, "plays": plays, "average_roi": average_roi, "win_rate": win_rate}


def main():
    # prepare_biggest_losers_csv()
    analyze_biggest_losers_csv()


if __name__ == "__main__":
    main()
