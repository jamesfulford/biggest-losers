from datetime import date

from src.data.polygon.grouped_aggs import get_today_grouped_aggs


def get_all_tickers_on_day(day: date, skip_cache=False):
    today_grouped_aggs = get_today_grouped_aggs(day, skip_cache=skip_cache)
    if not today_grouped_aggs:
        print(f'no data for {day}, cannot fetch candidates')
        return []
    return today_grouped_aggs["results"]
