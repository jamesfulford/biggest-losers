import mibian

import datetime
import logging
from typing import Iterator, Optional, Tuple
from src.chain.gramma import OptionSimulation
from src.chain.utils import filter_option_chain_for_calls, filter_option_chain_for_expiration, filter_option_chain_for_near_the_money, filter_option_chain_for_normality, filter_option_chain_for_out_of_the_money, filter_option_chain_for_puts
from src.data.finnhub.aggregate_candles import filter_candles_during_market_hours
from src.data.polygon.get_option_candles import get_option_candles
from src.data.polygon.option_chain import PolygonOptionChainContract, format_contract_specifier_to_polygon_option_ticker, get_option_chain
from src.data.finnhub import finnhub
from src.data.types.candles import CandleIntraday
from src.data.types.contracts import OptionCandleGetter, OptionContractSpecifier

from src.trading_day import now


def yield_contracts_toward_oom(contracts: list[PolygonOptionChainContract]) -> Iterator[PolygonOptionChainContract]:
    yield from sorted(contracts, key=lambda c: c['spec']['strike_price'], reverse=contracts[0]['spec']['contract_type'] == 'put')


def yield_contracts_from_soonest(contracts: list[PolygonOptionChainContract]) -> Iterator[Tuple[datetime.date, list[PolygonOptionChainContract]]]:
    contracts_by_expiration = {}
    for contract in contracts:
        contracts_by_expiration.setdefault(
            contract['spec']['expiration_date'], []).append(contract)

    for expiration_date, contracts in sorted(contracts_by_expiration.items()):
        yield expiration_date, contracts


def pick_favorite_contracts(contracts: list[PolygonOptionChainContract], current_price: float, candle_getter: OptionCandleGetter, option_price_range: tuple[int, int] = (1, 5)) -> Iterator[PolygonOptionChainContract]:
    contracts = filter_option_chain_for_normality(contracts)
    contracts = filter_option_chain_for_expiration(
        contracts, min_days_to_expiration=3, max_days_to_expiration=15)
    contracts = filter_option_chain_for_out_of_the_money(
        contracts, current_price)
    contracts = filter_option_chain_for_near_the_money(
        contracts, current_price, buffer=10)

    min_option_price, max_option_price = option_price_range

    for expiration_day, contracts in yield_contracts_from_soonest(contracts):

        for contract in yield_contracts_toward_oom(contracts):
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
                    f'{ticker} premium is too high {close}, looking at next expiration date')
                break

            if close < min_option_price:
                logging.debug(f'{ticker} premium is too low {close}')
                continue

            if volume < 1000:
                logging.debug(f'{ticker} volume is too low {volume}')
                continue

            # Does not matter very much for our timescale, so hardcoding
            # Using 1 year treasury rate ("risk free" rate of growth): https://www.investopedia.com/articles/active-trading/051415/how-why-interest-rates-affect-options.asp
            # https://ycharts.com/indicators/1_year_treasury_rate
            interest_rate = 2

            values = (current_price, contract['spec']['strike_price'],
                      interest_rate, contract['days_to_expiration'])
            c = mibian.BS(values, callPrice=close)
            c = mibian.BS(values, volatility=c.impliedVolatility)
            delta = c.callDelta if contract['spec']['contract_type'] == 'call' else c.putDelta

            if abs(delta) < 0.5:
                logging.debug(f'{ticker} delta is too low {delta}')
                continue

            logging.debug(f'{ticker} we like. {volume=} {close=}')
            yield contract


# TODO: deduplicate from gramma.py
def simulate_trade_in_options(underlying_symbol: str, start: datetime.datetime, end: datetime.datetime, upside: bool) -> Optional[OptionSimulation]:
    # Get necessary data
    # TODO: start and end may not be same day
    day = start.date()
    candles = finnhub.get_1m_candles(underlying_symbol, day, day)
    if not candles:
        print(f"{underlying_symbol} no candles found")
        raise ValueError(f"{underlying_symbol} no candles found")
    candles = filter_candles_during_market_hours(candles)
    current_price = [c for c in candles if c['datetime'] <= start][0]['close']

    # Find contract
    def get_truncated_option_candles(spec: OptionContractSpecifier, resolution: str, start_date: datetime.date, end_date: datetime.date) -> list[CandleIntraday]:
        candles = get_option_candles(spec, resolution, start_date, end_date)
        return [c for c in candles if c['datetime'] <= start]

    contracts = get_option_chain(underlying_symbol, day)
    if upside:
        contracts = filter_option_chain_for_calls(contracts)
    else:
        contracts = filter_option_chain_for_puts(contracts)
    contract = next(pick_favorite_contracts(
        contracts, current_price, get_truncated_option_candles), None)
    print(contract)
    if not contract:
        logging.debug("No contract found")
        return

    option_candles = get_option_candles(contract['spec'], '1', day, day)

    entry_candle = next(c for c in reversed(
        option_candles) if c['datetime'] <= start)
    exit_candle = next(c for c in option_candles if c['datetime'] >= end)
    holding_candles = [
        c for c in option_candles if c['datetime'] >= entry_candle['datetime'] and c['datetime'] <= exit_candle['datetime']]

    entry_candle = holding_candles[0]
    exit_candle = holding_candles[-1]
    peak_candle = max(holding_candles, key=lambda c: c['high'])
    valley_candle = min(holding_candles, key=lambda c: c['low'])

    open_price = entry_candle['open']
    close_price = exit_candle['close']
    high_price = peak_candle['high']
    low_price = valley_candle['low']

    was_low_first = valley_candle['datetime'] <= peak_candle['datetime']

    return {
        "open": open_price,
        "close": close_price,
        "high": high_price,
        "low": low_price,
        "was_low_first": was_low_first,

        "contract": contract,
    }


def main():
    print(simulate_trade_in_options(
        'AAPL', now() - datetime.timedelta(days=1, minutes=200), now() - datetime.timedelta(days=1, minutes=15), True))
