import re
from datetime import date, datetime, timedelta
import logging
import typing

from src.caching.basics import read_json_cache, write_json_cache
from src.data.polygon.polygon import _get_polygon_with_next_url_pagination
from src.data.types.contracts import OptionContractSpecifier
from src.trading_day import today, today_or_previous_trading_day


polygon_ticker_format = re.compile(r'O:([A-Z]+)([0-9]{6})([CP])([0-9]+)')


def extract_contract_specifier_from_polygon_option_ticker(ticker: str) -> OptionContractSpecifier:
    matches = polygon_ticker_format.match(ticker)
    if not matches:
        raise ValueError(f"Invalid ticker format: {ticker}")
    underlying_ticker, datestr, t, pricestr = matches.groups()
    return {
        'underlying_ticker': underlying_ticker,
        'contract_type': 'call' if 'C' == t else 'put',
        'expiration_date': datetime.strptime(datestr, '%y%m%d').date(),
        'strike_price': round(float(pricestr) / 1e3, 3),
    }


def format_contract_specifier_to_polygon_option_ticker(spec: OptionContractSpecifier) -> str:
    return f"O:{spec['underlying_ticker']}{spec['expiration_date'].strftime('%y%m%d')}{'C' if spec['contract_type'] == 'call' else 'P'}{str(int(spec['strike_price'] * 1e3)).rjust(8, '0')}"


class PolygonOptionChainContract(typing.TypedDict):
    spec: OptionContractSpecifier

    chain_as_of_date: date
    days_to_expiration: int

    shares_per_contract: int
    exercise_style: str  # american, european, bermudean
    primary_exchange: str
    cfi: str


def _get_option_chain_raw(underlying_symbol: str, day: date, expiration_end: date) -> list[dict]:
    return list(_get_polygon_with_next_url_pagination(
        "https://api.polygon.io/v3/reference/options/contracts",
        params={
            'underlying_ticker': underlying_symbol,
            'as_of': day.isoformat(),
            'expiration_date.lte': expiration_end.isoformat(),
            'limit': 1000,
            'sort': 'ticker',
        },
    ))


def _format_option_chain(raw_option_chain: list[dict], day: date) -> list[PolygonOptionChainContract]:
    return [{
        'spec': extract_contract_specifier_from_polygon_option_ticker(contract['ticker']),
        'chain_as_of_date': today_or_previous_trading_day(day),

        'shares_per_contract': contract['shares_per_contract'],

        'exercise_style': contract['exercise_style'],
        'cfi': contract['cfi'],
        'primary_exchange': contract['primary_exchange'],

        'days_to_expiration': (date.fromisoformat(contract['expiration_date']) - day).days,
    } for contract in raw_option_chain]


# reasoning for expiration_out default = 2 months
# - usually <1000 contracts, so we can download in 1 API call (limit 1000)
# - we usually don't care about contracts that are 2 months or more away (this might change)
def get_option_chain(underlying_symbol: str, day: date, expiration_out: timedelta = timedelta(days=60)) -> list[PolygonOptionChainContract]:
    # assuming will not change intraday, would hate to rebuild this cache every time
    # (does not include price information or volume, just listing of contracts)
    should_cache = day <= today()
    # TODO: does this change premarket?

    expiration_end = day + expiration_out
    cache_key = f"polygon/option_chains/{underlying_symbol}_{day.isoformat()}_{expiration_end.isoformat()}"

    if should_cache:
        cached = read_json_cache(cache_key)
        if cached:
            return _format_option_chain(cached, day)

    logging.info(
        f"Fetching option chain for {underlying_symbol} active on {day}")
    data = _get_option_chain_raw(underlying_symbol, day, expiration_end)

    if should_cache:
        write_json_cache(cache_key, data)

    return _format_option_chain(data, day)
