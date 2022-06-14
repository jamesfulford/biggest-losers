import datetime
import logging
import typing
import pandas as pd


from src import types
from src.results import from_backtest, metadata

import re
from src.data.polygon.option_chain import format_contract_specifier_to_polygon_option_ticker

from src.data.types.contracts import OptionContractSpecifier


TRANSACTION_FORMAT = re.compile(
    r'(Sold|Bought)( to Open| to Close|) ([X0-9]+) (.*) @ ([X0-9,.]*)')

# Test examples
"""
Bought 3 SCKT @ 8.8
Sold 3 SCKT @ 8.8

Bought X CANF @ X.1599

Bought 1 XLE Feb 11 2022 66.0 Call @ 1.42

Sold to Close 2 AMD Mar 18 2022 108.0 Call @ 3.08
Bought to Open 5 XLE Mar 25 2022 72.5 Call @ 1.39

Sold to Open 2 SPY Mar 18 2022 439.0 Call @ 1.46

Bought 1 SHOP @ 1,224.1
"""

OPTION_SYMBOL_FORMAT = re.compile(r'([A-Z]{1,5}) (.*) ([0-9.]+) (Call|Put)')

# Test examples
"""
AAPL Mar 25 2022 165.0 Call
QQQ Mar 25 2022 350.0 Call
SPY Mar 18 2022 440.0 Call
AMD Mar 18 2022 108.0 Call
AMD Mar 11 2022 106.0 Call
XLE Feb 11 2022 66.0 Call
"""


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Convert TD transactions downloaded from Mint.intuit.com to results')
    parser.add_argument('file', type=str)
    parser.add_argument('result_name', type=str)

    args = parser.parse_args()

    path = args.file
    result_name = args.result_name

    logging.info(
        f'Converting transactions from {path} to results {result_name}')

    orders = list(read_orders_from_mint_td_transactions(path))

    from_backtest.write_results(result_name, orders, metadata.Metadata(
        commit_id='', last_updated=datetime.datetime.now()))


def read_orders_from_mint_td_transactions(transactions_file_path) -> typing.Iterator[types.FilledOrder]:
    """
    Reads a mint td transactions file and returns a list of trades.
    """
    for r in pd.read_csv(transactions_file_path).to_dict('records'):
        if not r['Description'].startswith('Sold') and not r['Description'].startswith('Bought'):
            continue

        amount = float(r['Amount'])
        amount = amount if r['Transaction Type'] == 'credit' else -amount

        matches = TRANSACTION_FORMAT.match(r['Description'])
        if not matches:
            logging.warning("Unable to parse transaction, skipping: `%s`",
                            r['Description'])
            continue

        direction, _option_direction, quantity, symbol, price = matches.groups()

        is_stock = " " not in symbol
        is_option = "Call" in symbol or "Put" in symbol

        if not is_stock and not is_option:
            logging.warning(
                "Unable to handle non-stock/non-option transaction, skipping: `%s`", r['Description'])
            continue

        price = float(price.replace('X', '0').replace(',', ''))

        if quantity == 'X':  # infer it from transaction amount and execution price provided
            quantity = amount / price
        else:
            quantity = float(quantity)

        quantity = quantity if direction == 'Bought' else -quantity

        day = datetime.datetime.strptime(r['Date'], '%m/%d/%Y').date()
        dt = datetime.datetime.combine(
            day, datetime.datetime.max.time())  # assume at end of day

        if is_stock:
            core_value = abs(price*quantity)
            true_buffer = abs(abs(amount) - core_value)
            expected_buffer = 0.01  # reg fees, round up
            order = types.FilledOrder(
                intention=types.Intention(datetime=dt, symbol=symbol, extra={
                    "fees": {
                        # this is how much extra was tacked onto the trade outside of paying for the security
                        'observed': round(true_buffer, 2),
                        'expected': round(expected_buffer, 2),
                        'unexpected': round(true_buffer - expected_buffer, 2),
                    }
                }), symbol=symbol, quantity=quantity, price=price, datetime=dt)
        elif is_option:
            # NOTE: older options orders are formatted differently (says "to close" or "to open"), I have checked, it still works.
            # if option_direction:
            #     print(order, r['Description'], amount)
            price = 100 * price

            matches = OPTION_SYMBOL_FORMAT.match(symbol)
            if not matches:
                logging.warning(
                    "Unable to parse option symbol, skipping: `%s`", symbol)
                continue
            underlying_ticker, expiration_date, strike_price, contract_type = matches.groups()

            contract_type = 'call' if contract_type == 'Call' else 'put'
            strike_price = float(strike_price)
            expiration_date = datetime.datetime.strptime(
                expiration_date, '%b %d %Y').date()
            underlying_ticker = underlying_ticker.upper().strip()
            spec: OptionContractSpecifier = {
                "underlying_ticker": underlying_ticker,
                "contract_type": contract_type,
                "expiration_date": expiration_date,
                "strike_price": strike_price,
            }
            polygon_option_symbol = format_contract_specifier_to_polygon_option_ticker(
                spec)

            # calculate fees
            core_value = abs(price*quantity)
            true_buffer = abs(abs(amount) - core_value)
            # commission: 1.3c per share
            # reg fees: usually like 1c per share, varies, plugging in 2c per share for now
            # 1c buffer for rounding
            expected_buffer = abs(quantity * ((100*0.013 / 2) + 0.02)) + 0.01

            # if true_buffer > expected_buffer:
            #     logging.info(
            #         f'More fees than expected: {true_buffer:.2f} vs expected {expected_buffer:.2f} (on {r["Date"]} with {amount=:.2f}: {r["Description"]})')

            order = types.FilledOrder(
                intention=types.Intention(datetime=dt, symbol=polygon_option_symbol, extra={
                    "fees": {
                        # this is how much extra was tacked onto the trade outside of paying for the security
                        'observed': round(true_buffer, 2),
                        'expected': round(expected_buffer, 2),
                        'unexpected': round(true_buffer - expected_buffer, 2),
                    }
                }), symbol=polygon_option_symbol, quantity=quantity, price=price, datetime=dt)
        else:
            raise ValueError(f"Unhandled transaction type: {r['Description']}")

        # TODO: order fees analysis tools
        # if order.intention.extra['fees']['unexpected'] > 0 and order.is_option():
        #     print(order.intention.extra['fees']['unexpected'])
        yield order
