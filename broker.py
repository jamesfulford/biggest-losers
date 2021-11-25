import os
import requests


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
