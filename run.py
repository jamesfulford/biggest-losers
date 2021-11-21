
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
        'time_in_force': 'cls'
    }, headers=APCA_HEADERS)
    response.raise_for_status()
    return response.json()


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


def get_spy_change(today):
    spy_candle = enrich_grouped_aggs(fetch_grouped_aggs_with_cache(today))[
        "tickermap"]["SPY"]
    day = today - timedelta(days=1)
    spy_candle_yesterday = None
    while True:
        try:
            spy_candle_yesterday = enrich_grouped_aggs(
                fetch_grouped_aggs_with_cache(day))["tickermap"]["SPY"]
            break
        except Exception:
            pass
        day = day - timedelta(days=1)

    return (spy_candle["c"] - spy_candle_yesterday["c"]) / spy_candle_yesterday["c"]


def buy_biggest_losers_at_close(today, nominal):
    spy_change = get_spy_change(today)
    spy_change_upper_threshold = -.01
    if spy_change > spy_change_upper_threshold:
        print(
            f"SPY change is {round(100*spy_change, 1)}%, must be under {round(100*spy_change_upper_threshold, 1)}%, not buying")
        return

    losers = get_biggest_losers(today)

    losers = list(filter(lambda l: l["v"] > 100000, losers))
    losers = list(filter(lambda l: l["c"] < 1, losers))
    losers = list(filter(lambda l: ((l["c"] - l["o"]) / l["o"]) < -14, losers))
    losers = losers[:19]

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
    import sys
    datestr = ""
    try:
        datestr = sys.argv[1]
    except:
        pass

    if datestr:
        try:
            now = datetime.strptime(datestr, '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(
                f"error occurred while parsing datetime, will continue with {now}", e)

    today = now.date()
    hour = now.hour

    print(
        f"running on date {today} at hour {hour} in local timezone (should be America/New_York)")

    # (because APCA does not support buying warrants and arithmetic roi is better than geometric)
    #    -1%spy       *vol    p < 1   all d   top 19  intr<-14        !w |roi=4.005 a_roi=4.005 g_roi=3.192 plays=70 avg_roi=0.06 win%=0.571 days=61

    weekday = today.weekday()  # 0 is Monday, 4 is Friday
    if weekday not in [0, 1, 2, 3, 4]:
        print(f"today is not a good day for trading, exiting.")
        exit(0)

    # if before 3pm, close all positions (or submit sell orders for market open)
    # if after 3pm
    #  - check for open orders (so no double buying)
    #  - buy biggest losers

    nominal = 1000

    if hour >= 15 and hour < 16:
        print("3-4pm, buying biggest losers")
        # TODO: check purchasing power in case need to reduce quantity
        buy_biggest_losers_at_close(today, nominal)
    elif hour >= 19 or hour < 15:
        print("closing positions")
        print(liquidate())
    else:
        print("not time to do anything yet")
