
import time
import json
from datetime import date
from datetime import datetime, timedelta
import requests
import os


ALPACA_URL = os.environ['ALPACA_URL']
APCA_API_KEY_ID = os.environ['APCA_API_KEY_ID']
APCA_API_SECRET_KEY = os.environ['APCA_API_SECRET_KEY']

APCA_HEADERS = {
    'APCA-API-KEY-ID': APCA_API_KEY_ID,
    'APCA-API-SECRET-KEY': APCA_API_SECRET_KEY,
}


def buy_symbol_at_close(symbol, quantity):
    """
    Buy a symbol
    """
    response = requests.post(ALPACA_URL + '/v2/orders', json={
        'symbol': symbol,
        'qty': quantity,
        'side': 'buy',
        'type': 'market',
        # buy at close
        'time_in_force': 'day'
    }, headers=APCA_HEADERS)
    response.raise_for_status()
    return response.json()


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


def get_biggest_losers(today):
    yesterday = today - timedelta(days=1)
    yesterday_raw_grouped_aggs = fetch_grouped_aggs_with_cache(yesterday)
    # skip days where API returns no data (like trading holiday)
    if 'results' not in yesterday_raw_grouped_aggs:
        print(
            f'no results for {yesterday}, might have been a trading holiday, exiting')
        exit(0)

    yesterday_grouped_aggs = enrich_grouped_aggs(yesterday_raw_grouped_aggs)

    today_raw_grouped_aggs = fetch_grouped_aggs_with_cache(today)
    # skip days where API returns no data (like trading holiday)
    if 'results' not in today_raw_grouped_aggs:
        print(
            f'no results for {today}, might have been a trading holiday, exiting')
        exit(0)

    today_grouped_aggs = enrich_grouped_aggs(today_raw_grouped_aggs)

    #
    # go find biggest losers for the next day
    #

    # skip if wasn't present yesterday
    tickers_also_present_yesterday = list(filter(
        lambda t: t['T'] in yesterday_grouped_aggs['tickermap'], today_grouped_aggs['results']))

    for ticker in tickers_also_present_yesterday:
        previous_day_ticker = yesterday_grouped_aggs['tickermap'][ticker['T']]

        ticker['percent_change'] = (
            ticker['c'] - previous_day_ticker['c']) / previous_day_ticker['c']

    biggest_losers = sorted(tickers_also_present_yesterday,
                            key=lambda t: t['percent_change'])[:20]

    for loser in biggest_losers:
        loser['rank'] = biggest_losers.index(loser) + 1

    return biggest_losers


def buy_biggest_losers_at_close(today, nominal):

    losers = get_biggest_losers(today)

    losers = list(filter(lambda l: l["c"] < 5, losers))

    positions = get_positions()
    print(positions)

    for loser in losers:

        quantity = round((nominal / loser['c']) - 0.5)
        print(
            f"Submitting buy order of {loser['T']} {quantity} (current price {loser['c']}, target amount {quantity * loser['c']}) at close")
        try:
            buy_symbol_at_close(loser["T"], quantity)
        except Exception as e:
            print(e.response.status_code, e.response.json())


def liquidate():
    response = requests.delete(
        ALPACA_URL + '/v2/positions', headers=APCA_HEADERS)
    response.raise_for_status()
    return response.json()


def get_positions():
    response = requests.get(
        ALPACA_URL + '/v2/positions', headers=APCA_HEADERS)
    response.raise_for_status()
    return response.json()


if __name__ == '__main__':

    now = datetime.now()
    try:
        import sys
        datestr = sys.argv[1]
        now = datetime.strptime(datestr, '%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(
            "error occurred while parsing datetime, will continue with {now}", e)

    today = now.date()
    hour = now.hour

    print(
        f"running on date {today} at hour {hour} in local timezone (should be America/New_York)")

    weekday = today.weekday()  # 0 is Monday, 4 is Friday
    if weekday not in [1, 2, 3]:
        print(f"today is not a good day for trading, exiting.")
        exit(0)

    # TODO: work based on current time
    # if before 3pm, close all positions (or submit sell orders for market open)
    # if after 3pm
    #  - check for open orders (so no double buying)
    #  - buy biggest losers

    if hour >= 15 and hour < 16:
        print("3-4pm, buying biggest losers")
        # TODO: check purchasing power in case need to reduce quantity
        nominal = 5
        buy_biggest_losers_at_close(today, nominal)
    elif hour >= 20 or hour <= 10:
        print("closing positions")
        print(liquidate())
    else:
        print("not time to do anything yet")
