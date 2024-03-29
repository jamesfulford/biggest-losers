from datetime import date
import logging

from src.data.polygon.grouped_aggs import Ticker, get_today_grouped_aggs


def get_all_tickers_on_day(day: date) -> list[Ticker]:
    today_grouped_aggs = get_today_grouped_aggs(day)
    if not today_grouped_aggs:
        logging.info(f'no data for {day}, cannot fetch candidates')
        return []
    return today_grouped_aggs["results"]
