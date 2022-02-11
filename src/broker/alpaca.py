import json
import logging
import os
from datetime import datetime, timedelta
from time import sleep
from typing import Union
import uuid

import requests

from src.broker.dry_run import DRY_RUN


ALPACA_URL = os.environ["ALPACA_URL"]
APCA_API_KEY_ID = os.environ["APCA_API_KEY_ID"]
APCA_API_SECRET_KEY = os.environ["APCA_API_SECRET_KEY"]

APCA_HEADERS = {
    "APCA-API-KEY-ID": APCA_API_KEY_ID,
    "APCA-API-SECRET-KEY": APCA_API_SECRET_KEY,
}


def _log_response(response: requests.Response):
    logging.debug(
        f"ALPACA: {response.status_code} {response.url} => {response.text}")


def _get_alpaca(url):
    response = requests.get(ALPACA_URL + url, headers=APCA_HEADERS)
    _log_response(response)
    if response.status_code == 429:
        logging.info("Rate limited, waiting...")
        sleep(5)
        return _get_alpaca(url)
    response.raise_for_status()
    return response.json()


def _add_feather_finance_algo_label(order: dict, algo_name: Union[str, None] = None):
    if algo_name:
        order["client_order_id"] = f"{algo_name}_FF_{uuid.uuid4()}"
    return order


def _warn_for_fractional_shares(quantity: float):
    if round(quantity) != quantity:
        logging.warning(
            f"quantity {quantity} is not an integer, broker will use fractional shares")


def _place_order(body: dict, algo_name: Union[str, None] = None) -> requests.Response:
    body = _add_feather_finance_algo_label(body, algo_name=algo_name)
    logging.debug(f"_place_order: {json.dumps(body, sort_keys=True)}")

    if DRY_RUN:
        logging.info(f'DRY_RUN: _place_order({body=})')
        return

    response = requests.post(
        ALPACA_URL + "/v2/orders",
        json=body,
        headers=APCA_HEADERS,
    )
    _log_response(response)
    response.raise_for_status()
    return response.json()


def buy_symbol_at_close(symbol: str, quantity: float, algo_name: Union[str, None] = None):
    """
    Buy a symbol at close
    """
    _warn_for_fractional_shares(quantity)

    return _place_order({
        "symbol": symbol,
        "qty": quantity,
        "side": "buy",
        "type": "market",
        # buy at close
        "time_in_force": "cls",
    }, algo_name=algo_name)


def buy_symbol_market(symbol: str, quantity: float, algo_name: Union[str, None] = None):
    """
    Buy a symbol now
    """
    _warn_for_fractional_shares(quantity)

    return _place_order({
        "symbol": symbol,
        "qty": quantity,
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
    }, algo_name=algo_name)


def sell_symbol_market(symbol: str, quantity: float, algo_name: Union[str, None] = None):
    """
    Sell a symbol now
    """
    _warn_for_fractional_shares(quantity)

    return _place_order({
        "symbol": symbol,
        "qty": quantity,
        "side": "sell",
        "type": "market",
        "time_in_force": "day",
    }, algo_name=algo_name)


def sell_symbol_at_open(symbol: str, quantity: float, algo_name: Union[str, None] = None):
    """
    Sell a symbol
    """
    _warn_for_fractional_shares(quantity)

    return _place_order({
        "symbol": symbol,
        "qty": quantity,
        "side": "sell",
        "type": "market",
        # sell at open
        "time_in_force": "opg",
    }, algo_name=algo_name)


def wait_until_order_filled(order_id: str):
    while True:
        order = _get_alpaca(f"/v2/orders/{order_id}")
        if order["status"] == "filled":
            return order
        logging.debug(f"{order_id} status: {order['status']}, waiting...")
        sleep(1)


def place_oto(
    symbol: str,
    quantity: float,
    take_profit_limit: float,
    algo_name: Union[str, None] = None
):
    _warn_for_fractional_shares(quantity)

    return _place_order({
        "side": "buy",
        "symbol": symbol,
        "type": "market",
        "qty": str(quantity),
        "time_in_force": "gtc",
        "order_class": "oto",
        "take_profit": {
            "limit_price": str(take_profit_limit),
        },
    }, algo_name=algo_name)


def place_oco(
    symbol: str,
    quantity: float,
    take_profit_limit: float,
    stop_loss_stop: float,
    stop_loss_limit: float = None,
    algo_name: Union[str, None] = None
):
    _warn_for_fractional_shares(quantity)

    body = {
        "side": "sell",
        "symbol": symbol,
        "type": "limit",
        "qty": str(quantity),
        "time_in_force": "gtc",
        "order_class": "oco",
        "take_profit": {"limit_price": str(take_profit_limit)},
        "stop_loss": {
            "stop_price": str(stop_loss_stop),
        },
    }
    if stop_loss_limit:
        body["stop_loss"]["limit_price"] = str(stop_loss_limit)

    return _place_order(body, algo_name=algo_name)


def cancel_order(order_id: str) -> None:
    response = requests.delete(
        ALPACA_URL + f"/v2/orders/{order_id}",
        headers=APCA_HEADERS,
    )
    _log_response(response)
    response.raise_for_status()


def cancel_all_orders() -> None:
    response = requests.delete(
        ALPACA_URL + f"/v2/orders",
        headers=APCA_HEADERS,
    )
    _log_response(response)
    response.raise_for_status()


def _build_position(raw_position):
    return {
        "symbol": raw_position["symbol"],
        "qty": float(raw_position["qty"]),
        "avg_entry_price": float(raw_position["avg_entry_price"]),
    }


def get_positions():
    return list(map(_build_position, _get_alpaca("/v2/positions")))


def _build_account(account):
    """
    {
        "account_blocked": false,
        "account_number": "PA36YT3M6YH7",
        "accrued_fees": "0",
        "buying_power": "106894.62",
        "cash": "106894.62",
        "created_at": "2022-02-04T18:36:11.527497Z",
        "crypto_status": "ACTIVE",
        "currency": "USD",
        "daytrade_count": 2,
        "daytrading_buying_power": "0",
        "equity": "106894.62",
        "id": "27a4a8a0-ac20-46ac-9896-38e1c15a9217",
        "initial_margin": "0",
        "last_equity": "101977.71",
        "last_maintenance_margin": "29083.48",
        "long_market_value": "0",
        "maintenance_margin": "0",
        "multiplier": "1",
        "non_marginable_buying_power": "106894.62",
        "pattern_day_trader": false,
        "pending_transfer_in": "0",
        "portfolio_value": "106894.62",
        "regt_buying_power": "106894.62",
        "short_market_value": "0",
        "shorting_enabled": false,
        "sma": "100105.49",
        "status": "ACTIVE",
        "trade_suspended_by_user": false,
        "trading_blocked": false,
        "transfers_blocked": false
    }
    """
    return {
        "id": account['account_number'],
        # on alpaca, all are margin account type. CASH | MARGIN
        "type": "MARGIN",
        # less than just cash, it's only cash we can use right now.
        "cash": float(account['cash']),
        "equity": float(account['equity']),
        "long_market_value": float(account['long_market_value']),
    }


def get_account():
    return _build_account(_get_alpaca("/v2/account"))


def get_filled_orders(start: datetime, end: datetime):
    # inclusive (API is exclusive)
    # sorted from earliest to latest

    limit = 500

    def _fetch_closed_orders(after: datetime, until: datetime):
        logging.debug(f"fetching up to {limit} closed orders after {after}")
        results = _get_alpaca(
            f"/v2/orders?status=closed&after={after}&until={until}&direction=asc&limit={limit}"
        )

        if len(results) == limit:
            # because asc, [-1] is latest
            # subtract 1s so we don't miss any orders. We have to deduplicate them later.
            latest_submitted_at = datetime.strptime(
                results[-1]["submitted_at"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ) - timedelta(seconds=1)

            if latest_submitted_at <= after:
                # this will happen if {limit} orders are submitted in the same second
                raise Exception(
                    "too many results in same 1s period {latest_submitted_at}"
                )

            new_results = _fetch_closed_orders(latest_submitted_at, until)

            return results + new_results

        return results

    results = _fetch_closed_orders(
        start - timedelta(seconds=1), end + timedelta(seconds=1)
    )

    # deduplicate
    id_set = set()
    deduped_results = []
    for result in results:
        if result["id"] not in id_set:
            deduped_results.append(result)
            id_set.add(result["id"])

    # filled orders are sorted from earliest to latest
    deduped_results = list(
        filter(lambda x: x["status"] == "filled", deduped_results))

    # should already be sorted, but put this here to be safe
    deduped_results.sort(key=lambda x: x["submitted_at"])

    return deduped_results


def main():
    logging.getLogger().setLevel(logging.DEBUG)
    buy_symbol_market("AAPL", 1.1, algo_name=None)
