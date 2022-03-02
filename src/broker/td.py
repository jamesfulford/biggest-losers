from datetime import datetime
import json
import logging
import os
from typing import List, Union
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


def _log_response(response: requests.Response):
    logging.debug(
        f"TD: {response.status_code} {response.url} => {response.text}")


def _warn_for_fractional_shares(quantity: float):
    if round(quantity) != quantity:
        logging.warning(
            f"quantity {quantity} is not an integer, broker will use fractional shares")


def _get(url: str, **kwargs):
    response = requests.get(
        "https://api.tdameritrade.com" + url, **kwargs, headers=_get_headers())
    _log_response(response)
    response.raise_for_status()
    return response

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

    if account_type == "CASH":
        cash_available_for_trading = account['securitiesAccount']['currentBalances']['cashAvailableForTrading']
    else:
        cash_available_for_trading = account['securitiesAccount']['currentBalances']['availableFunds']

    equity = account['securitiesAccount']['currentBalances']['liquidationValue']

    # TODO: this might behave differently in margin accounts
    # long_market_value = account['securitiesAccount']['currentBalances']['longMarketValue']
    long_market_value = equity - cash_available_for_trading

    return {
        "id": account['securitiesAccount']["accountId"],
        # on alpaca, all are margin account type. CASH | MARGIN
        "type": account_type,
        # less than just cash, it's only cash we can use right now.
        "cash": round(cash_available_for_trading, 2),
        "equity": round(equity, 2),
        "long_market_value": round(long_market_value, 2),
        # cash accounts only, not on Alpaca
        "unsettled_cash": round(account['securitiesAccount']['currentBalances']['unsettledCash'], 2) if account_type == 'CASH' else 0,
    }


def get_account(account_id: str = None):
    if not account_id:
        account_id = get_account_id()

    response = _get(f"/v1/accounts/{account_id}")

    return _build_account(response.json())


def get_accounts():
    response = _get(f"/v1/accounts")

    return list(map(_build_account, response.json()))


#
# Orders
#
def get_filled_orders(start: datetime, end: datetime, account_id: str = None):
    if not account_id:
        account_id = get_account_id()

    response = _get(f"/v1/accounts/{account_id}/orders", params={
        'status': 'filled',
        'fromEnteredTime': start.date().isoformat(),
        'toEnteredTime': end.date().isoformat(),
    })

    filled_orders = list(
        filter(bool, list(map(_build_order, response.json()))))
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
    if len(order.get('orderLegCollection', [])) != 1:
        logging.warning(f"{order['orderId']} has multiple legs, skipping")
        return None

    instruction = order['orderLegCollection'][0]

    if "orderActivityCollection" not in order:
        logging.warning(
            f"{order['orderId']} has no orderActivityCollection, skipping")
        return None

    average_fill_price = _get_average_fill_price(order)

    return {
        'id': str(order['orderId']),
        'account_id': str(order['accountId']),  # TD-specific
        'status': order['status'].lower(),
        'symbol': instruction["instrument"]["symbol"].replace("+", ".WS"),
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


def _build_position(position):
    """
    Map TD API position to a dict similar to Alpaca API position
    {
        "shortQuantity": 0.0,
        "averagePrice": 6.325,
        "currentDayProfitLoss": 0.0,
        "currentDayProfitLossPercentage": 0.0,
        "longQuantity": 1.0,
        "settledLongQuantity": 0.0,
        "settledShortQuantity": 0.0,
        "instrument": {
            "assetType": "EQUITY",
            "cusip": "82968B103",
            "symbol": "SIRI"
        },
        "marketValue": 6.33,
        "maintenanceRequirement": 1.9,
        "currentDayCost": 6.33,
        "previousSessionLongQuantity": 0.0
    }
    """
    return {
        "symbol": position["instrument"]["symbol"],
        "qty": position["longQuantity"],
        "avg_price": position["averagePrice"],
    }


def get_positions(account_id: str = None):
    if not account_id:
        account_id = get_account_id()

    response = _get(f"/v1/accounts/{account_id}", params={
        'fields': 'positions'
    })

    raw_account = response.json()
    positions = raw_account['securitiesAccount'].get(
        'positions', [])  # if no positions, no 'positions' key

    final_positions = []
    for position in positions:
        new_position = _build_position(position)
        asset_type = position.get("instrument", {}).get("assetType", "")
        # ignore money markets, not an actual position
        if asset_type not in ["CASH_EQUIVALENT"]:
            final_positions.append(new_position)
    return final_positions

#
# Placing orders
#


def _place_order(body: dict, account_id: Union[str, None] = None):
    if not account_id:
        account_id = get_account_id()

    logging.debug(f"_place_order: {json.dumps(body, sort_keys=True)}")

    if DRY_RUN:
        logging.info(f"DRY_RUN: _place_order({body=})")
        return

    response = requests.post(
        f"https://api.tdameritrade.com/v1/accounts/{account_id}/orders", json=body, headers=_get_headers())
    _log_response(response)
    response.raise_for_status()
    return response


def normalize_symbol(symbol: str):
    """
    TD API doesn't like ., replace with /
    """
    return symbol.replace('.', '/')


def buy_symbol_at_close(symbol: str, quantity: float, account_id: Union[str, None] = None, algo_name: Union[str, None] = None):
    symbol = normalize_symbol(symbol)
    _warn_for_fractional_shares(quantity)
    _place_order({
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
    }, account_id=account_id)


def buy_symbol_market(symbol: str, quantity: float, account_id: Union[str, None] = None, algo_name: Union[str, None] = None):
    symbol = normalize_symbol(symbol)
    _warn_for_fractional_shares(quantity)
    _place_order({
        "orderType": "MARKET",
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
    }, account_id=account_id)


def sell_symbol_market(symbol: str, quantity: float, account_id: Union[str, None] = None, algo_name: Union[str, None] = None):
    symbol = normalize_symbol(symbol)
    _warn_for_fractional_shares(quantity)

    _place_order({
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
    }, account_id=account_id)


def sell_symbol_at_open(symbol: str, quantity: float, account_id: Union[str, None] = None, algo_name: Union[str, None] = None):
    symbol = normalize_symbol(symbol)
    _warn_for_fractional_shares(quantity)

    response = _place_order({
        # There is no MARKET_ON_OPEN order type
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
    }, account_id=account_id)

    if not response:
        return {
            "status_code": 200,
            "body": b"DRY_RUN",
        }

    return {
        "status_code": response.status_code,
        "body": response.text,
    }


def print_accounts_summary():
    accounts = get_accounts()
    user_info = get_user_info()
    print(f"User {user_info['userId']}:")
    for account_info in user_info["accounts"]:
        account = next(
            filter(lambda a: a['id'] == account_info["accountId"], accounts), None)

        is_primary = user_info['primaryAccountId'] == account_info["accountId"]
        is_margin = account_info['authorizations']['marginTrading']

        equity = account['equity']
        cash = account['cash']

        print(
            f" {'*' if is_primary else ' '}{account_info['displayName']:<16} {'MARGIN' if is_margin else '':<6} '{account['id']}' {equity=:>10.2f} {cash=:>10.2f}")
        # print(account_info["accountId"], account_info['displayName'],
        #       account_info['authorizations']['marginTrading'], account['equity'])


try:
    get_account_id()
except KeyError as e:
    logging.fatal(
        f"cannot find TD_ACCOUNT_ID environment variable. Set TD_ACCOUNT_ID environment variable to one of these:")
    print_accounts_summary()
    exit(1)


def _get_price_rounded(quote: dict, price_key: str):
    return round(quote[price_key], quote['digits'])


def get_quotes(symbols: List[str]):
    """
    "NRGU": {
        "52WkHigh": 356.0,
        "52WkLow": 85.89,
        "askId": "P",
        "askPrice": 339.9,
        "askSize": 300,
        "assetMainType": "EQUITY",
        "assetType": "EQUITY",
        "bidId": "P",
        "bidPrice": 327.72,
        "bidSize": 100,
        "bidTick": " ",
        "closePrice": 330.0,
        "cusip": "06367V105",
        "delayed": false,
        "description": "MicroSectors U.S. Big Oil Index 3X Leveraged ETN",
        "digits": 2,
        "divAmount": 0.0,
        "divDate": "",
        "divYield": 0.0,
        "exchange": "p",
        "exchangeName": "PACIFIC",
        "highPrice": 356.0,
        "lastId": "P",
        "lastPrice": 337.99,
        "lastSize": 0,
        "lowPrice": 327.0,
        "marginable": true,
        "mark": 337.99,
        "markChangeInDouble": 7.99,
        "markPercentChangeInDouble": 2.4212,
        "nAV": 0.0,
        "netChange": 7.99,
        "netPercentChangeInDouble": 2.4212,
        "openPrice": 340.55,
        "peRatio": 0.0,
        "quoteTimeInLong": 1646172261975,
        "realtimeEntitled": true,
        "regularMarketLastPrice": 337.99,
        "regularMarketLastSize": 4,
        "regularMarketNetChange": 7.99,
        "regularMarketPercentChangeInDouble": 2.4212,
        "regularMarketTradeTimeInLong": 1646169000002,
        "securityStatus": "Normal",
        "shortable": true,
        "symbol": "NRGU",
        "totalVolume": 257805,
        "tradeTimeInLong": 1646172091728,
        "volatility": 0.2284
    }
    """
    response = _get(f"/v1/marketdata/quotes", params={
        "symbol": ",".join(symbols)
    })

    quotes = {}
    for symbol, quote in response.json().items():
        quotes[symbol] = {
            "ask": _get_price_rounded(quote, 'askPrice'),
            "bid": _get_price_rounded(quote, 'bidPrice'),
            "spread": round(quote['askPrice'] - quote['bidPrice'], quote['digits']),
            "day_candle": {
                "open": _get_price_rounded(quote, 'openPrice'),
                "high": _get_price_rounded(quote, 'highPrice'),
                "low": _get_price_rounded(quote, 'lowPrice'),
                "close": _get_price_rounded(quote, 'closePrice'),
                "volume": quote['totalVolume'],
            },
        }

    return quotes


def get_quote(symbol: str):
    return get_quotes([symbol])[symbol]


def get_user_info():
    """
    {
        "userId" : "jamespfulford",
        "userCdDomainId" : "A000000085603460",
        "primaryAccountId" : "279989255",
        "lastLoginTime" : "2022-03-01T22:16:17+0000",
        "tokenExpirationTime" : "2022-03-01T22:49:28+0000",
        "loginTime" : "2022-03-01T22:19:28+0000",
        "accessLevel" : "CUS",
        "stalePassword" : false,
        "professionalStatus" : "NON_PROFESSIONAL",
        "quotes" : {
            "isNyseDelayed" : false,
            "isNasdaqDelayed" : false,
            "isOpraDelayed" : false,
            "isAmexDelayed" : false,
            "isCmeDelayed" : true,
            "isIceDelayed" : true,
            "isForexDelayed" : true
        },
        "exchangeAgreements" : {
            "OPRA_EXCHANGE_AGREEMENT" : "ACCEPTED",
            "NASDAQ_EXCHANGE_AGREEMENT" : "ACCEPTED",
            "NYSE_EXCHANGE_AGREEMENT" : "ACCEPTED"
        },
        "accounts" : [
            {
                "accountId" : "252321094",
                "displayName" : "margin",
                "accountCdDomainId" : "A000000093786939",
                "company" : "AMER",
                "segment" : "AMER",
                "acl" : "BPCCDRDTDWESF7G1G3G5G7GKGLH1H3H5LTM1MAPNQSRFSDTETFTOTTUAURXBXNXO",
                "authorizations" : {
                    "apex" : false,
                    "levelTwoQuotes" : false,
                    "stockTrading" : true,
                    "marginTrading" : true,
                    "streamingNews" : false,
                    "optionTradingLevel" : "NONE",
                    "streamerAccess" : true,
                    "advancedMargin" : true,
                    "scottradeAccount" : false
                }
            },
            ...
        ]
    }
    """
    return _get("/v1/userprincipals").json()


def get_watchlists():
    return _get("/v1/accounts/watchlists").json()


def main():
    # print_accounts_summary()
    update_watchlist('James 1', ["AAPL", "XLE"])

    for w in get_watchlists():
        print(w["name"], w["accountId"], w["watchlistId"], list(
            map(lambda i: i['instrument']['symbol'], w["watchlistItems"])))


def update_watchlist(target_name: str, symbols: List[str]):
    """
    Overwrites (or creates) watchlist in primary account with given symbols.
    NOTE: TDAmeritrade does not propagate updates to TOS clients quickly. Restarting clients seems to be best.
    https://www.reddit.com/r/thinkorswim/comments/or2uyj/watchlist_updates_using_tda_api_not_behaving/
    """
    user_info = get_user_info()
    primary_account_id = user_info['primaryAccountId']

    watchlists = get_watchlists()
    w = next(filter(lambda w: w['name'] == target_name and w['accountId']
             == primary_account_id, watchlists), None)

    new_watchlist = {
        "name": target_name,
        "watchlistItems": list(map(lambda symbol: {
            "instrument": {
                "symbol": symbol,
            },
        }, symbols)),
    }
    if not w:
        print(f"Creating watchlist {target_name}")
        r = requests.post(
            f"https://api.tdameritrade.com/v1/accounts/{primary_account_id}/watchlists", json=new_watchlist, headers=_get_headers())
        _log_response(r)
        r.raise_for_status()
        return

    r = requests.put(
        f"https://api.tdameritrade.com/v1/accounts/{w['accountId']}/watchlists/{w['watchlistId']}", json=new_watchlist, headers=_get_headers())
    _log_response(r)
    r.raise_for_status()
