
from datetime import date
import logging
import pprint
from typing import Iterator
from src.chain.utils import filter_option_chain_for_calls, filter_option_chain_for_expiration, filter_option_chain_for_near_the_money, filter_option_chain_for_normality, filter_option_chain_for_out_of_the_money, filter_option_chain_for_puts
from src.data.finnhub.aggregate_candles import filter_candles_during_market_hours
from src.data.polygon.get_candles import get_candles
from src.data.polygon.get_option_candles import get_option_candles
from src.data.polygon.option_chain import PolygonOptionChainContract, format_contract_specifier_to_polygon_option_ticker, get_option_chain
import src.data.finnhub.finnhub as finnhub
from src.data.types.contracts import OptionCandleGetter


def pick_favorite_contracts(contracts: list[PolygonOptionChainContract], current_price: float, candle_getter: OptionCandleGetter, option_price_range: tuple[int, int] = (1, 5)) -> Iterator[PolygonOptionChainContract]:
    """
    Picks normal contracts expiring soon (but not too soon) that are out of the money but close.
    This should find contracts with high gammas. TODO: confirm
    """
    contracts = filter_option_chain_for_normality(contracts)
    contracts = filter_option_chain_for_expiration(
        contracts, min_days_to_expiration=3, max_days_to_expiration=15)
    contracts = filter_option_chain_for_out_of_the_money(
        contracts, current_price)
    contracts = filter_option_chain_for_near_the_money(
        contracts, current_price, buffer=10)

    contracts_by_expiration = {}
    for contract in contracts:
        contracts_by_expiration.setdefault(
            contract['spec']['expiration_date'], []).append(contract)

    min_option_price, max_option_price = option_price_range
    for _expiration_date, contracts in sorted(contracts_by_expiration.items()):
        for contract in sorted(contracts, key=lambda c: c['spec']['strike_price'], reverse=contracts[0]['spec']['contract_type'] == 'put'):
            ticker = format_contract_specifier_to_polygon_option_ticker(
                contract['spec'])

            candles = candle_getter(contract['spec'], '1',
                                    contract['chain_as_of_date'], contract['chain_as_of_date'])
            if not candles:
                logging.debug(f"{ticker} no candles found")
                continue
            close = candles[-1]['close']
            volume = sum(c['volume'] for c in candles)

            if close > max_option_price:
                logging.debug(
                    f'{ticker} is too high {close}, looking at next expiration date')
                break

            if close < min_option_price:
                logging.debug(f'{ticker} is too low {close}')
                continue

            if volume < 1000:
                logging.debug(f'{ticker} volume is too low {volume}')
                continue

            logging.debug(f'{ticker} we like. {volume=} {close=}')
            yield contract


def main():
    underlying_symbol = 'AAPL'
    day = date(2022, 4, 27)

    # Get necessary data
    candles = finnhub.get_1m_candles(underlying_symbol, day, day)
    if not candles:
        print(f"{underlying_symbol} no candles found")
        return
    candles = filter_candles_during_market_hours(candles)
    current_price = candles[0]['open']
    upside = False

    # Find contract
    contracts = get_option_chain(underlying_symbol, day)
    if upside:
        contracts = filter_option_chain_for_calls(contracts)
    else:
        contracts = filter_option_chain_for_puts(contracts)
    contract = next(pick_favorite_contracts(
        contracts, current_price, get_option_candles), None)
    if not contract:
        print('No contract found')
        return
    pprint.pprint(contract)
