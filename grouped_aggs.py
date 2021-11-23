import os
from datetime import date, datetime
import time
import requests
from cache import read_json_cache, write_json_cache

API_KEY = os.environ['POLYGON_API_KEY']
HOME = os.environ['HOME']


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
