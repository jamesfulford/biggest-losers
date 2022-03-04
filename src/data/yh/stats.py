from datetime import date, timedelta
import logging
import os
from typing import Union
import requests

from src.cache import get_matching_entries, read_json_cache, write_json_cache
from src.trading_day import get_last_market_close, now


def _get_headers():
    return {
        'x-rapidapi-host': "yh-finance.p.rapidapi.com",
        'x-rapidapi-key': os.environ["X_RAPIDAPI_KEY_YH_FINANCE"],
    }


def _fetch_stats(symbol: str):
    response = requests.get("https://yh-finance.p.rapidapi.com/stock/v3/get-statistics", headers=_get_headers(), params={
        "symbol": symbol,
    })
    response.raise_for_status()
    return response.json()


def _get_stats_cache_key(symbol: str, day: date):
    return f"yh_v3_stats_{symbol}_{day.isoformat()}"


def _get_latest_cache_entry_key(symbol: str, day: date) -> Union[str, None]:
    entries = get_matching_entries(f"yh_v3_stats_{symbol}_")
    entries = list(filter(lambda entry: entry <=
                   _get_stats_cache_key(symbol, day), entries))
    entries.sort(key=lambda entry: date.fromisoformat(entry.split("_")[-1]))
    return entries[-1] if entries else None


def _get_stats(symbol: str):
    # Assuming values we care about are updated at most daily
    cache_key = _get_stats_cache_key(
        symbol, get_last_market_close(now()).date())

    should_cache = True

    if should_cache:
        cached = read_json_cache(cache_key)
        if cached:
            return cached

    logging.info(f"fetching stats for {symbol}")
    data = _fetch_stats(symbol)

    if should_cache:
        write_json_cache(cache_key, data)

    return data


#
# Short Interest
#


def _parse_previous_report_date(data: dict) -> date:
    return date.fromisoformat(
        data["defaultKeyStatistics"]["sharesShortPreviousMonthDate"]["fmt"])


def _parse_current_report_date(data: dict) -> date:
    return date.fromisoformat(
        data["defaultKeyStatistics"]["dateShortInterest"]["fmt"])


def _build_short_interest_format_from_previous_data(data: dict, key: str):
    return {
        "shares_short": data["defaultKeyStatistics"]["sharesShortPriorMonth"]["raw"],

        "report_date": _parse_previous_report_date(data),
        "_from_previous_report": True,
        "_cache_entry_key": key,
    }


def _build_short_interest_format(data: dict, key: str):
    return {
        "shares_short": data["defaultKeyStatistics"]["sharesShort"]["raw"],

        "previous_report": _build_short_interest_format_from_previous_data(data, key),

        "report_date": _parse_current_report_date(data),
        "_from_previous_report": False,
        "_cache_entry_key": key,
    }


def get_short_interest(symbol: str, day: date = None) -> Union[dict, None]:
    """
    Get short interest for a given symbol.
    Returns None if `day` is too long ago for the cache.
    """
    if day is None:
        day = date.today()

    assert day <= date.today()

    key = _get_latest_cache_entry_key(symbol, date.today())
    if not key:
        logging.info(
            f"get_short_interest: No entries found in cache for {symbol}, fetching...")
        data = _get_stats(symbol)
        return _build_short_interest_format(data, key)

    # keep scrolling until we find an applicable report
    # (store report's data in variable `data`)
    is_latest_report = True
    while True:
        data = read_json_cache(key)

        if not data:
            print(key)
            exit()

        previous_report_date = _parse_previous_report_date(data)
        current_report_date = _parse_current_report_date(data)
        time_between_reports = (current_report_date - previous_report_date)
        estimated_next_report_date = current_report_date + time_between_reports

        if time_between_reports.days > 32:
            logging.info(
                f"get_short_interest: {time_between_reports.days=}  ({previous_report_date} to {current_report_date})")

        # A: in current report range: stop scrolling, we have the data
        if day >= current_report_date and day < estimated_next_report_date:
            return _build_short_interest_format(data, key)

        # B: if prior to current report:
        if day < current_report_date:
            # B.1: if previous report applies: stop scrolling, we have the data
            if day >= previous_report_date:
                return _build_short_interest_format_from_previous_data(data, key)

            # B.2: if previous report does not apply:

            previous_cache_key = _get_latest_cache_entry_key(
                symbol, (current_report_date - timedelta(days=1)))

            # B.2.1: if have prior cache entry: scroll back to it, then try again
            if previous_cache_key:
                key = previous_cache_key
                is_latest_report = False
                continue

            # B.2.2: no prior cache entry; return None
            logging.warn(
                f"get_short_interest: insufficient cache data to get short info for {symbol} on {day}. Use reports on or after {previous_report_date}.")
            return None

        # C: if we expect a report now or soon:
        if day >= estimated_next_report_date:
            # C.1: we checked the latest report: fetch latest
            if is_latest_report:
                logging.info(
                    "get_short_interest: new report should be ready, fetching...")
                data = _get_stats(symbol)
                return _build_short_interest_format(data, key)

            # C.2: there's a missing report in the cache between two entries: return None
            logging.warn(
                f"get_short_interest: gap in cache including {day}, covers to {estimated_next_report_date} (estimated), most applicable report is {current_report_date}.")
            # NOTE: in theory, we could provide data from the current report, while it may be outdated
            return None


def main():
    print({
        "date(2022, 1, 1)": get_short_interest("AAPL", date(2022, 1, 1)),
        "date(2022, 1, 13)": get_short_interest("AAPL", date(2022, 1, 13)),
        "date(2022, 1, 14)": get_short_interest("AAPL", date(2022, 1, 14))['report_date'],
        "date(2022, 1, 15)": get_short_interest("AAPL", date(2022, 1, 15))['report_date'],
        "date(2022, 2, 14)": get_short_interest("AAPL", date(2022, 2, 14))['report_date'],
        "date(2022, 2, 15)": get_short_interest("AAPL", date(2022, 2, 15))['report_date'],
        "date(2022, 2, 16)": get_short_interest("AAPL", date(2022, 2, 16))['report_date'],
    })
