from datetime import datetime
import json
import os
import requests

from src.pathing import get_paths
from src.broker.dry_run import DRY_RUN


def get_account_id():
    return os.environ['TD_ACCOUNT_ID']


def _get_token():
    path = get_paths()['data']["inputs"]["td-token_json"]
    with open(path) as f:
        return json.load(f)


def _get_access_token():
    return _get_token()['access_token']


def _get_headers():
    return {
        'Authorization': f"Bearer {_get_access_token()}",
    }

#
# Accounts
#


def _build_account(account):
    """
    Map TD API account to a dict similar to Alpaca API account
    {
        "securitiesAccount": {
            "type": "CASH",
            "accountId": "279989255",
            "roundTrips": 0,
            "isDayTrader": false,
            "isClosingOnlyRestricted": false,
            "initialBalances": {
                "accruedInterest": 0,
                "cashAvailableForTrading": 123.45,
                "cashAvailableForWithdrawal": 123.45,
                "cashBalance": 123.45,
                "bondValue": 0,
                "cashReceipts": 0,
                "liquidationValue": 150.0,
                "longOptionMarketValue": 0,
                "longStockValue": 26.55,
                "moneyMarketFund": 0,
                "mutualFundValue": 0,
                "shortOptionMarketValue": 0,
                "shortStockValue": 0,
                "isInCall": false,
                "unsettledCash": 0,
                "cashDebitCallValue": 0,
                "pendingDeposits": 0,
                "accountValue": 150.0
            },
            "currentBalances": {
                "accruedInterest": 0,
                "cashBalance": 123.45,
                "cashReceipts": 0,
                "longOptionMarketValue": 0,
                "liquidationValue": 150.0,
                "longMarketValue": 26.55,
                "moneyMarketFund": 0,
                "savings": 0,
                "shortMarketValue": 0,
                "pendingDeposits": 0,
                "cashAvailableForTrading": 123.45,
                "cashAvailableForWithdrawal": 123.45,
                "cashCall": 0,
                "longNonMarginableMarketValue": 123.45,
                "totalCash": 123.45,
                "shortOptionMarketValue": 0,
                "mutualFundValue": 0,
                "bondValue": 0,
                "cashDebitCallValue": 0,
                "unsettledCash": 0
            },
            "projectedBalances": {
                "cashAvailableForTrading": 123.45,
                "cashAvailableForWithdrawal": 123.45
            }
        }
    }
    """
    account_type = account['securitiesAccount']["type"]

    return {
        "id": account['securitiesAccount']["accountId"],
        # on alpaca, all are margin account type. CASH | MARGIN
        "type": account_type,
        # less than just cash, it's only cash we can use right now.
        "cash": account['securitiesAccount']['currentBalances']['cashBalance'],
        "equity": account['securitiesAccount']['currentBalances']['liquidationValue'],
        "long_market_value": account['securitiesAccount']['currentBalances']['longMarketValue'],
        # cash accounts only, not on Alpaca
        "unsettled_cash": account['securitiesAccount']['currentBalances']['unsettledCash'] if account_type == 'CASH' else 0,
    }


def get_account(account_id: str = None):
    if not account_id:
        account_id = get_account_id()

    response = requests.get(
        f"https://api.tdameritrade.com/v1/accounts/{account_id}", headers=_get_headers())

    response.raise_for_status()
    return _build_account(response.json())


def get_accounts():
    response = requests.get(
        f"https://api.tdameritrade.com/v1/accounts", headers=_get_headers())

    response.raise_for_status()
    return list(map(_build_account, response.json()))


#
# Orders
#
def get_filled_orders(start: datetime, end: datetime, account_id: str = None):
    if not account_id:
        account_id = get_account_id()

    response = requests.get(
        f"https://api.tdameritrade.com/v1/accounts/{account_id}/orders", headers=_get_headers(), params={
            'status': 'filled',
            'fromEnteredTime': start.date().isoformat(),
            'toEnteredTime': end.date().isoformat(),
        })

    response.raise_for_status()
    filled_orders = list(map(_build_order, response.json()))
    filled_orders.sort(key=lambda x: x['filled_at'])
    return filled_orders


def _get_average_fill_price(order):
    total_cost = 0
    total_quantity = 0
    for activity in order['orderActivityCollection']:
        # average fill price of execution legs of each activity in the order
        total_cost += sum(list(map(lambda x: x['price']
                          * x['quantity'], activity['executionLegs'])))
        # conveniently already totaled for me:
        total_quantity += activity['quantity']

    return total_cost / total_quantity


def _build_order(order):
    """
    Map TD API order to a dict similar to Alpaca API order
    {
        "session": "NORMAL",
        "duration": "DAY",
        "orderType": "LIMIT",
        "complexOrderStrategyType": "NONE",
        "quantity": 100.0,
        "filledQuantity": 100.0,
        "remainingQuantity": 0.0,
        "requestedDestination": "AUTO",
        "destinationLinkName": "NITE",
        "price": 28.0,
        "orderLegCollection": [
            {
            "orderLegType": "EQUITY",
            "legId": 1,
            "instrument": {
                "assetType": "EQUITY",
                "cusip": "53814L108",
                "symbol": "LTHM"
            },
            "instruction": "BUY",
            "positionEffect": "OPENING",
            "quantity": 100.0
            }
        ],
        "orderStrategyType": "SINGLE",
        "orderId": 5609066619,
        "cancelable": false,
        "editable": false,
        "status": "FILLED",
        "enteredTime": "2021-12-05T03:00:14+0000",
        "closeTime": "2021-12-06T14:30:02+0000",
        "tag": "API_TOS_ADMIN:KEY: Ctrl O",
        "accountId": 279989255,
        "orderActivityCollection": [
            {
            "activityType": "EXECUTION",
            "executionType": "FILL",
            "quantity": 100.0,
            "orderRemainingQuantity": 0.0,
            "executionLegs": [
                {
                "legId": 1,
                "quantity": 100.0,
                "mismarkedQuantity": 0.0,
                "price": 27.67,
                "time": "2021-12-06T14:30:02+0000"
                }
            ]
            }
        ]
    }
    """

    instruction = order['orderLegCollection'][0]
    if len(order['orderLegCollection']) > 1:
        print(f"WARNING: {order['orderId']} has multiple legs, skipping")
        return None

    average_fill_price = _get_average_fill_price(order)

    return {
        'id': str(order['orderId']),
        'account_id': str(order['accountId']),  # TD-specific
        'status': order['status'].lower(),
        'symbol': instruction["instrument"]["symbol"],
        'filled_qty': order['filledQuantity'],
        'filled_avg_price': average_fill_price,
        'side': instruction["instruction"],
        # "%Y-%m-%dT%H:%M:%S.%fZ"
        'filled_at': order["closeTime"].replace("+0000", ".000Z"),
        'submitted_at': order["enteredTime"].replace("+0000", ".000Z"),
    }

#
# Positions
#


def get_positions(account_id: str = None):
    # TODO: implement this
    pass

#
# Placing orders
#


def buy_symbol_at_close(symbol: str, quantity: int, account_id: str = None):
    if not account_id:
        account_id = get_account_id()

    symbol = normalize_symbol(symbol)

    if DRY_RUN:
        print(f'DRY_RUN: buy_symbol_at_close({symbol}, {quantity})')
        return

    response = requests.post(f"https://api.tdameritrade.com/v1/accounts/{account_id}/orders", json={
        "orderType": "MARKET_ON_CLOSE",
        "session": "NORMAL",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {
                "instruction": "BUY",
                "quantity": quantity,
                "instrument": {
                    "symbol": symbol,
                    "assetType": "EQUITY"
                }
            }
        ]
    }, headers=_get_headers())

    response.raise_for_status()


def normalize_symbol(symbol: str):
    """
    TD API doesn't like ., replace with /
    """
    return symbol.replace('.', '/')


def sell_symbol_at_open(symbol: str, quantity: int, account_id: str = None):
    if not account_id:
        account_id = get_account_id()

    symbol = normalize_symbol(symbol)

    if DRY_RUN:
        print(f'DRY_RUN: sell_symbol_at_open({symbol}, {quantity})')
        return

    response = requests.post(f"https://api.tdameritrade.com/v1/accounts/{account_id}/orders", json={
        # There is no MARKET_ON_OPEN order type
        # TODO: evaluate whether this acts like Alpaca's "opg" order with duration "DAY"
        "orderType": "MARKET",
        "session": "NORMAL",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {
                "instruction": "SELL",
                "quantity": quantity,
                "instrument": {
                    "symbol": symbol,
                    "assetType": "EQUITY"
                }
            }
        ]
    }, headers=_get_headers())

    print(response.json())
    response.raise_for_status()
    return response.json()


try:
    get_account_id()
except KeyError as e:
    print(f"ERROR: cannot find TD_ACCOUNT_ID environment variable. Set TD_ACCOUNT_ID environment variable to one of these:")
    for account in get_accounts():
        print(
            f"  '{account['id']}' (has ${round(account['cash'], 2)} in cash)")
    exit(1)


def main():
    print('development...')
