import os
import requests
from datetime import date, datetime, timedelta


ALPACA_URL = os.environ['ALPACA_URL']
APCA_API_KEY_ID = os.environ['APCA_API_KEY_ID']
APCA_API_SECRET_KEY = os.environ['APCA_API_SECRET_KEY']

APCA_HEADERS = {
    'APCA-API-KEY-ID': APCA_API_KEY_ID,
    'APCA-API-SECRET-KEY': APCA_API_SECRET_KEY,
}

DRY_RUN = 'DRY_RUN' in os.environ
if DRY_RUN:
    print('DRY RUN, will not execute any trades')
else:
    print('LIVE RUN, will execute trades')


def _get_alpaca(url):
    response = requests.get(ALPACA_URL + url, headers=APCA_HEADERS)
    response.raise_for_status()
    return response.json()


def buy_symbol_at_close(symbol, quantity):
    """
    Buy a symbol
    """
    if DRY_RUN:
        print(f'DRY_RUN: buy_symbol_at_close({symbol}, {quantity})')
        return

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


def liquidate():
    if DRY_RUN:
        print(f'DRY_RUN: liquidate()')
        return

    response = requests.delete(
        ALPACA_URL + '/v2/positions', headers=APCA_HEADERS)
    response.raise_for_status()
    return response.json()


def get_positions():
    return _get_alpaca('/v2/positions')


def get_account():
    return _get_alpaca('/v1/account')


def get_open_orders():
    return _get_alpaca('/v1/orders')


def get_filled_orders(start: date, end: date):
    # inclusive (API is exclusive)
    # sorted from earliest to latest

    limit = 500

    def _fetch_closed_orders(after: datetime, until: datetime):
        print(f"fetching up to {limit} closed orders after {after}")
        results = _get_alpaca(
            f'/v2/orders?status=closed&after={after}&until={until}&direction=asc&limit={limit}')

        if len(results) == limit:
            # because asc, [-1] is latest
            # subtract 1s so we don't miss any orders. We have to deduplicate them later.
            latest_submitted_at = datetime.strptime(
                results[-1]["submitted_at"], "%Y-%m-%dT%H:%M:%S.%fZ") - timedelta(seconds=1)

            if latest_submitted_at <= after:
                # this will happen if {limit} orders are submitted in the same second
                raise Exception(
                    "too many results in same 1s period {latest_submitted_at}")

            new_results = _fetch_closed_orders(latest_submitted_at, until)

            return results + new_results

        return results

    results = _fetch_closed_orders(
        start - timedelta(seconds=1), end + timedelta(seconds=1))

    # deduplicate
    id_set = set()
    deduped_results = []
    for result in results:
        if result["id"] not in id_set:
            deduped_results.append(result)
            id_set.add(result["id"])

    # filled orders are sorted from earliest to latest
    deduped_results = list(
        filter(lambda x: x["status"] == 'filled', deduped_results))

    # should already be sorted, but put this here to be safe
    deduped_results.sort(key=lambda x: x["submitted_at"])

    return deduped_results
