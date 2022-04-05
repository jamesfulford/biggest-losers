from datetime import date, datetime, timedelta, timezone
import json
import logging
import os
from typing import Optional, cast
import requests
from src.data.td.td import get_quote

from src.outputs.pathing import get_paths
from src.broker.dry_run import DRY_RUN
from src.trading_day import MARKET_TIMEZONE


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
        f"TD: {response.status_code} {response.request.method} {response.url} => {response.text}")


def _warn_for_fractional_shares(quantity: float):
    if round(quantity) != quantity:
        logging.warning(
            f"quantity {quantity} is not an integer, broker will use fractional shares")


def _build_account_specific_base_url(url: str, account_id: Optional[str] = None) -> str:
    if not account_id:
        account_id = get_account_id()
    return f"/v1/accounts/{account_id}{url}"


def _get(url: str, **kwargs) -> requests.Response:
    return _request(url, "GET", **kwargs)


def _request(url: str, method: str, **kwargs) -> requests.Response:
    response = requests.request(
        method, "https://api.tdameritrade.com" + url, **kwargs, headers=_get_headers())
    _log_response(response)
    response.raise_for_status()
    return response

#
# Accounts
#


def _build_account(account):
    """
    Map TD API account to a dict similar to Alpaca API account
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


def get_account(account_id: Optional[str] = None):
    response = _get(_build_account_specific_base_url(
        "", account_id=account_id))

    return _build_account(response.json())


def get_accounts():
    response = _get(f"/v1/accounts")

    return list(map(_build_account, response.json()))


#
# Orders
#
def get_filled_orders(start: datetime, end: datetime, account_id: Optional[str] = None):
    if not account_id:
        account_id = get_account_id()

    response = _get(f"/v1/accounts/{account_id}/orders", params={
        'status': 'filled',
        'fromEnteredTime': start.date().isoformat(),
        'toEnteredTime': end.date().isoformat(),
    })

    filled_orders = list(
        filter(bool, list(map(_build_order, response.json()))))
    filled_orders = cast(list[dict], filled_orders)
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


def _build_order(order) -> Optional[dict]:
    """
    Map TD API order to a dict similar to Alpaca API order
    Assumes order has been filled.
    """
    if len(order.get('orderLegCollection', [])) != 1:
        # TODO: resolve multi-leg orders
        logging.warning(f"{order['orderId']} has multiple legs, skipping")
        return None

    instruction = order['orderLegCollection'][0]

    order_type_map = {
        'LIMIT': 'LIMIT',
        'MARKET': 'MARKET',
        'STOP': 'STOP',
        'STOP_LIMIT': 'STOP_LIMIT',
        'TRAILING_STOP': 'TRAILING_STOP',

        'MARKET_ON_CLOSE': 'MARKET',  # tif=cls

        # no mapping to Alpaca
        'TRAILING_STOP_LIMIT': 'UNKNOWN',
        'EXERCISE': 'UNKNOWN',  # probably options
    }
    order_type = order_type_map.get(order["orderType"], "UNKNOWN")
    if order_type == "UNKNOWN":
        logging.warning(
            f"{order['orderId']} has unexpected order type {order['orderType']}")

    duration_to_tif_map = {
        'DAY': 'DAY',
        'GOOD_TILL_CANCEL': 'GTC',
        'FILL_OR_KILL': 'FILL_OR_KILL',
    }
    tif = duration_to_tif_map.get(order["duration"], "day")
    if order['orderType'] == 'MARKET_ON_CLOSE':
        tif = 'cls'

    status_map = {
        'ACCEPTED': 'ACCEPTED',
        # happens outside market hours (saw at 10:30pm)
        'PENDING_ACTIVATION': 'ACCEPTED',
        'FILLED': "FILLED",
        'QUEUED': "NEW",
        'CANCELED': "CANCELED",
        'EXPIRED': 'EXPIRED',
        'REPLACED': 'REPLACED',
        'PENDING_CANCEL': 'PENDING_CANCEL',
        'PENDING_REPLACE': 'PENDING_REPLACE',
        'REJECTED': 'REJECTED',

        # not sure what these mean or how they are mapped to Alpaca's statuses
        # https://alpaca.markets/docs/trading/orders/#order-lifecycle
        'WORKING': 'UNKNOWN',
        'AWAITING_PARENT_ORDER': 'UNKNOWN',
        'AWAITING_CONDITION': 'UNKNOWN',
        'AWAITING_MANUAL_REVIEW': 'UNKNOWN',
        'AWAITING_UR_OUT': 'UNKNOWN',
    }
    status = status_map.get(order["status"], "UNKNOWN")
    if status == "UNKNOWN":
        logging.warning(
            f"{order['orderId']} has unexpected status {order['status']}")

    new_order = {
        'id': str(order['orderId']),
        'symbol': instruction["instrument"]["symbol"].replace("+", ".WS"),
        'qty': order["quantity"],

        'side': instruction["instruction"],
        'type': order_type,
        'limit_price': order.get("price", None),
        'stop_price': order.get("stopPrice", None),
        'tif': tif,
        'status': status,

        'submitted_at': datetime.strptime(
            order["enteredTime"].replace("+0000", ".000Z"), "%Y-%m-%dT%H:%M:%S.%fZ")
        .replace(tzinfo=timezone.utc)
        .astimezone(MARKET_TIMEZONE),

        'account_id': str(order['accountId']),  # TD-specific
    }

    if order['status'] == "FILLED":

        if "orderActivityCollection" not in order:
            logging.warning(
                f"filled order {order['orderId']} has no orderActivityCollection, skipping")
            return None

        average_fill_price = _get_average_fill_price(order)

        new_order.update({
            'filled_qty': order['filledQuantity'],
            'filled_avg_price': average_fill_price,
            # "%Y-%m-%dT%H:%M:%S.%fZ"
            'filled_at': datetime.strptime(
                order["closeTime"].replace("+0000", ".000Z"), "%Y-%m-%dT%H:%M:%S.%fZ")
            .replace(tzinfo=timezone.utc)
            .astimezone(MARKET_TIMEZONE),
        })

    return new_order

#
# Positions
#


def _build_position(position):
    """
    Map TD API position to a dict similar to Alpaca API position
    """
    return {
        "symbol": position["instrument"]["symbol"],
        "qty": position["longQuantity"],
        "avg_price": position["averagePrice"],
    }


def get_positions(account_id: Optional[str] = None):
    response = _get(_build_account_specific_base_url("", account_id=account_id), params={
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


def _place_order(body: dict, account_id: Optional[str] = None):
    logging.debug(f"_place_order: {json.dumps(body, sort_keys=True)}")

    if DRY_RUN:
        logging.info(f"DRY_RUN: _place_order({body=})")
        return

    return _request(_build_account_specific_base_url("/orders", account_id=account_id), "POST", json=body)


def normalize_symbol(symbol: str):
    """
    TD API doesn't like ., replace with /
    """
    return symbol.replace('.', '/')


def buy_symbol_at_close(symbol: str, quantity: float, account_id: Optional[str] = None, algo_name: Optional[str] = None):
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


def buy_symbol_market(symbol: str, quantity: float, account_id: Optional[str] = None, algo_name: Optional[str] = None):
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


def sell_symbol_market(symbol: str, quantity: float, account_id: Optional[str] = None, algo_name: Optional[str] = None):
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


def sell_symbol_at_open(symbol: str, quantity: float, account_id: Optional[str] = None, algo_name: Optional[str] = None):
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
        if not account:
            continue

        is_primary = user_info['primaryAccountId'] == account_info["accountId"]
        is_margin = account_info['authorizations']['marginTrading']

        equity = account['equity']
        cash = account['cash']

        print(
            f" {'*' if is_primary else ' '}{account_info['displayName']:<16} {'MARGIN' if is_margin else '':<6} '{account['id']}' {equity=:>10.2f} {cash=:>10.2f}")


def get_user_info():
    return _get("/v1/userprincipals").json()


def get_watchlists():
    return _get("/v1/accounts/watchlists").json()


def update_watchlist(target_name: str, symbols: list[str]):
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
        logging.info(f"Creating watchlist {target_name}")
        _request(_build_account_specific_base_url("/watchlists",
                 account_id=primary_account_id), "POST", json=new_watchlist)
        return

    _request(_build_account_specific_base_url(
        f"/watchlists/{w['watchlistId']}", account_id=w['accountId']), "POST", json=new_watchlist)


def _round_price(price: float) -> float:
    return round(price, 2 if price > 1 else 4)


def buy_limit(symbol: str, quantity: int, price: float, allow_premarket: bool = False, gtc: bool = False, account_id: Optional[str] = None):
    _warn_for_fractional_shares(quantity)
    _place_order({
        "orderType": "LIMIT",
        "price": str(_round_price(price)),
        "session": "SEAMLESS" if allow_premarket else "NORMAL",
        "duration": "GOOD_TILL_CANCEL" if gtc else "DAY",
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


def sell_limit(symbol: str, quantity: int, price: float, allow_premarket: bool = False, gtc: bool = False, account_id: Optional[str] = None):
    _warn_for_fractional_shares(quantity)
    _place_order({
        "orderType": "LIMIT",
        "price": str(_round_price(price)),
        "session": "SEAMLESS" if allow_premarket else "NORMAL",
        "duration": "GOOD_TILL_CANCEL" if gtc else "DAY",
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


def buy_limit_thru(symbol: str, quantity: int, buffer: float = .05, **limit_args):
    quote = get_quote(symbol)
    price = _round_price(quote['ask'] + buffer)
    logging.debug(
        f"Buying {quantity} shares of {symbol} at {price} ({quote['ask']} + {buffer})")
    buy_limit(symbol, quantity, price, **limit_args)


def sell_limit_thru(symbol: str, quantity: int, buffer: float = .05, **limit_args):
    quote = get_quote(symbol)
    price = _round_price(quote['bid'] - buffer)
    logging.debug(
        f"Buying {quantity} shares of {symbol} at {price} ({quote['bid']} - {buffer})")
    sell_limit(symbol, quantity, price, **limit_args)


def cancel_order(order_id: str, account_id: Optional[str] = None):
    return _request(_build_account_specific_base_url(f"/orders/{order_id}", account_id=account_id), "DELETE")


def get_open_orders(account_id: Optional[str] = None) -> list[dict]:
    """
    Gets all orders.
    This is TD-specific format, not mapped to shared open-order json format
    """
    orders = _get(_build_account_specific_base_url(
        "/orders", account_id=account_id), params={
            'fromEnteredTime': (date.today() - timedelta(days=90)).isoformat(),
            'toEnteredTime': date.today().isoformat()
    }).json()
    orders = list(filter(lambda o: o['cancelable'], orders))
    orders = list(map(_build_order, orders))
    orders = cast(list[dict], list(filter(bool, orders)))
    return orders


def cancel_all_orders(account_id: Optional[str] = None):
    orders = get_open_orders(account_id=account_id)
    for order in orders:
        cancel_order(order['id'], account_id=account_id)


def place_oco(
    symbol: str,
    quantity: float,
    take_profit_limit: float,
    stop_loss_stop: float,
    stop_loss_limit: Optional[float] = None,
    account_id: Optional[str] = None,
):
    symbol = normalize_symbol(symbol)
    _warn_for_fractional_shares(quantity)

    stop_loss_order = {
        "orderType": "STOP",
        "session": "NORMAL",
        "duration": "GOOD_TILL_CANCEL",
        "orderStrategyType": "SINGLE",
        "stopPrice": str(_round_price(stop_loss_stop)),
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
    }
    if stop_loss_limit:
        stop_loss_order['price'] = str(_round_price(stop_loss_limit))
        stop_loss_order['orderType'] = "STOP_LIMIT"
    _place_order({
        "orderStrategyType": "OCO",
        "childOrderStrategies": [
            {
                "orderType": "LIMIT",
                "session": "NORMAL",
                "price": str(_round_price(take_profit_limit)),
                "duration": "GOOD_TILL_CANCEL",
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
            },
            stop_loss_order
        ]
    }, account_id=account_id)


def main():
    cancel_all_orders()


try:
    get_account_id()
except KeyError as e:
    logging.fatal(
        f"cannot find TD_ACCOUNT_ID environment variable. Set TD_ACCOUNT_ID environment variable to one of these:")
    print_accounts_summary()
    exit(1)
