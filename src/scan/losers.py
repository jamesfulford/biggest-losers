from datetime import date

from src.criteria import is_etf, is_right, is_stock, is_unit, is_warrant
from src.trading_day import generate_trading_days
from src.data.polygon.grouped_aggs import get_cache_prepared_date_range_with_leadup_days, get_last_2_candles
from src.csv_dump import write_csv
from src.data.polygon.grouped_aggs import get_today_grouped_aggs


#
# _on_day: used for LIVE and BACKTEST
# - all filtering logic should be here
# - all critical indicators should be enriched in here
#
# Some tips:
# - try to filter on OHLCV first before getting daily candles or calculating indicators
def get_all_candidates_on_day(today: date, skip_cache=False):
    today_grouped_aggs = get_today_grouped_aggs(today, skip_cache=skip_cache)
    if not today_grouped_aggs:
        print(f'no data for {today}, cannot fetch candidates')
        return None

    tickers = today_grouped_aggs['results']
    tickers = list(filter(lambda t: t["v"] > 100000, tickers))

    # get yesterday's close
    new_tickers = []
    for ticker in tickers:
        last_2_candles = get_last_2_candles(today, ticker["T"])
        if not last_2_candles:
            continue
        today_candle, yesterday_candle = tuple(last_2_candles)

        ticker["yesterday_c"] = yesterday_candle["c"]
        new_tickers.append(ticker)
    tickers = new_tickers

    for ticker in tickers:
        ticker['percent_change'] = (
            ticker['c'] - ticker['yesterday_c']) / ticker['yesterday_c']

    tickers = list(filter(lambda t: t["percent_change"] < -.2, tickers))

    # must be of acceptable type
    new_tickers = []
    for ticker in tickers:
        ticker['is_stock'] = is_stock(ticker['T'], day=today)
        ticker['is_etf'] = is_etf(ticker['T'], day=today)
        ticker['is_warrant'] = is_warrant(ticker['T'], day=today)
        ticker['is_unit'] = is_unit(ticker['T'], day=today)
        ticker['is_right'] = is_right(ticker['T'], day=today)

        if not any((ticker['is_stock'], ticker['is_etf'], ticker['is_warrant'], ticker['is_unit'], ticker['is_right'])):
            continue
        new_tickers.append(ticker)
    tickers = new_tickers

    # adding rank
    tickers = sorted(tickers, key=lambda t: -t['percent_change'])
    for ticker in tickers:
        ticker['rank'] = tickers.index(ticker) + 1

    return tickers


def get_all_candidates_between_days(start: date, end: date):
    for day in generate_trading_days(start, end):
        for candidate in get_all_candidates_on_day(day) or []:
            candidate["day_of_action"] = day
            yield candidate


def build_row(candidate: dict):
    return {
        "day_of_action": candidate['day_of_action'],
        # ticker insights
        "T": candidate['T'],
        "is_stock": candidate['is_stock'],
        "is_etf": candidate['is_etf'],
        "is_warrant": candidate['is_warrant'],
        "is_unit": candidate['is_unit'],
        "is_right": candidate['is_right'],

        # day_of_action stats
        "o": candidate["o"],
        "h": candidate["h"],
        "l": candidate["l"],
        "c": candidate["c"],
        "v": candidate["v"],
        "n": candidate["n"],

        # rank
        "rank": candidate["rank"],

        # indicators
        "vw": candidate["vw"],
        "yesterday_c": candidate["yesterday_c"],
        "percent_change": candidate["percent_change"],
    }


def prepare_biggest_losers_csv(path: str, start: date, end: date):
    write_csv(
        path,
        map(build_row, get_all_candidates_between_days(start, end)),
        headers=[
            "day_of_action",
            "T",
            "is_stock",
            "is_etf",
            "is_warrant",
            "is_unit",
            "is_right",
            "o",
            "h",
            "l",
            "c",
            "v",
        ]
    )


def prepare_csv():
    from src.pathing import get_paths

    path = get_paths()["data"]["outputs"]["losers_csv"]

    start, end = get_cache_prepared_date_range_with_leadup_days(0)
    start = max(start, date(2021, 1, 1))  # TODO: undo
    end = min(end, date(2021, 12, 31))  # TODO: undo

    print("start:", start)
    print("end:", end)
    print("estimated trading days:", len(
        list(generate_trading_days(start, end))))

    prepare_biggest_losers_csv(path, start=start, end=end)
