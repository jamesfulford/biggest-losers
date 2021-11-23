from datetime import datetime, timedelta
import requests
import os

from grouped_aggs import enrich_grouped_aggs, fetch_grouped_aggs_with_cache


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
    #   -1%spy       *vol    p < 5   all d   top 8   intr<-8 !w |roi=7.548 a_roi=7.548 g_roi=7.142 plays=227 avg_roi=0.04 win%=0.507 days=148

    spy_change = get_spy_change(today)
    spy_change_upper_threshold = -.01
    if spy_change > spy_change_upper_threshold:
        print(
            f"SPY change is {round(100*spy_change, 1)}%, must be under {round(100*spy_change_upper_threshold, 1)}%, not buying")
        return

    losers = get_biggest_losers(today)

    losers = list(filter(lambda l: l["v"] > 100000, losers))
    losers = list(filter(lambda l: l["c"] < 5, losers))
    losers = list(filter(lambda l: ((l["c"] - l["o"]) / l["o"]) < -8, losers))
    losers = list(filter(lambda l: l["rank"] <= 8, losers))

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
    #   -1%spy       *vol    p < 5   all d   top 8   intr<-8 !w |roi=7.548 a_roi=7.548 g_roi=7.142 plays=227 avg_roi=0.04 win%=0.507 days=148

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
