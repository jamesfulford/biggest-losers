from datetime import date
from src.trading_day import generate_trading_days
from src.grouped_aggs import get_cache_prepared_date_range_with_leadup_days
from src.csv_dump import write_csv
from src.criteria import is_etf, is_right, is_stock, is_unit, is_warrant
from src.overnights import collect_overnights
from src.criteria import is_etf, is_right, is_stock, is_warrant, is_unit
from src.grouped_aggs import get_today_grouped_aggs, get_last_trading_day_grouped_aggs


def get_volume_movers(today, skip_cache=False):
    today_grouped_aggs = get_today_grouped_aggs(today, skip_cache=skip_cache)
    if not today_grouped_aggs:
        print(f'no data for {today}, cannot fetch')
        return None
    yesterday_grouped_aggs = get_last_trading_day_grouped_aggs(today)

    # skip if wasn't present yesterday
    tickers_also_present_yesterday = list(filter(
        lambda t: t['T'] in yesterday_grouped_aggs['tickermap'], today_grouped_aggs['results']))

    for ticker in tickers_also_present_yesterday:
        previous_day_ticker = yesterday_grouped_aggs['tickermap'][ticker['T']]

        ticker['percent_volume_change'] = (
            ticker['v'] - previous_day_ticker['v']) / (previous_day_ticker['v'] + 1)  # added 1 to fix a divide by 0 issue
        ticker['previous_day_ticker'] = previous_day_ticker

    movers = list(
        filter(lambda t: t['percent_volume_change'] > 0, tickers_also_present_yesterday))

    movers = list(
        filter(lambda t: is_stock(t["T"], today) or is_etf(t["T"], today) or is_warrant(
            t["T"], today) or is_right(t["T"], today) or is_unit(t["T"], today), movers)
    )

    movers = sorted(movers, key=lambda t: -t['percent_volume_change'])

    for mover in movers:
        mover['rank'] = movers.index(mover) + 1

    volume_movers = list(
        filter(lambda t: t['rank'] <= 10, movers)
    )

    return volume_movers
    # return list(map(lambda mover: {
    #     "day_of_action": today,
    #     "mover_day_of_action": mover,
    #     "mover_day_before": yesterday_grouped_aggs['tickermap'][mover['T']],
    # }, volume_movers))


def get_all_volume_movers_between(start: date, end: date):
    volume_movers = []
    for mover in collect_overnights(
        start, end, get_actions_on_day=lambda day: get_volume_movers(day)
    ):
        volume_movers.append(mover)

    return volume_movers


def prepare_volume_movers_csv(path: str, start: date, end: date):
    biggest_movers = get_all_volume_movers_between(start, end)

    def yield_movers():
        for mover in biggest_movers:
            day_of_action = mover["day_of_action"]
            mover_day_of_action = mover["mover_day_of_action"]
            # mover_day_before = mover["mover_day_before"]
            mover_day_after = mover["day_after"]

            yield {
                "day_of_action": day_of_action,
                "percent_change": mover_day_of_action["percent_volume_change"],
                "rank": mover_day_of_action["rank"],
                "ticker": mover_day_of_action["T"],
                # day_of_action stats
                "open_day_of_action": mover_day_of_action["o"],
                "high_day_of_action": mover_day_of_action["h"],
                "low_day_of_action": mover_day_of_action["l"],
                "close_day_of_action": mover_day_of_action["c"],
                "volume_day_of_action": mover_day_of_action["v"],
                # TODO: previous day stats
                # "open_day_before": mover_day_before["o"],
                # "high_day_before": mover_day_before["h"],
                # "low_day_before": mover_day_before["l"],
                # "close_day_before": mover_day_before["c"],
                # "volume_day_before": mover_day_before["v"],
                # TODO: add day_after stats
                # type of ticker
                "is_stock": is_stock(mover_day_of_action["T"], day_of_action),
                "is_etf": is_etf(mover_day_of_action["T"], day_of_action),
                "is_warrant": is_warrant(mover_day_of_action["T"], day_of_action),
                "is_right": is_right(mover_day_of_action["T"], day_of_action),
                "is_unit": is_unit(mover_day_of_action["T"], day_of_action),

            }

    write_csv(
        path,
        yield_movers(),
        headers=[
            "day_of_action",
            "rank",
            "percent_change",
            "ticker",
            #
            "open_day_before",
            "high_day_before",
            "low_day_before",
            "close_day_before",
            "volume_day_before",
            #
            "open_day_of_action",
            "high_day_of_action",
            "low_day_of_action",
            "close_day_of_action",
            "volume_day_of_action",
        ],
    )


def prepare_csv():
    from src.pathing import get_paths

    path = get_paths()["data"]["outputs"]["volume_movers_csv"]

    start, end = get_cache_prepared_date_range_with_leadup_days(1)
    start = date(2021, 12, 1)
    end = date(2021, 12, 31)
    print("start:", start)
    print("end:", end)
    print("estimated trading days:", len(
        list(generate_trading_days(start, end))))

    prepare_volume_movers_csv(path, start, end)
