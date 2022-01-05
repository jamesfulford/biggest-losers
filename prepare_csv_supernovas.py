from datetime import date
import os
from src.criteria import is_warrant
from src.grouped_aggs import get_cache_prepared_date_range_with_leadup_days

from src.overnights import collect_overnights
from src.supernovas import get_supernovas
from src.csv_dump import write_csv
from src.trading_day import generate_trading_days


def get_all_supernovas(start: date, end: date):
    novas = []
    for day in generate_trading_days(start, end):
        today_supernovas = get_supernovas(day, pct=0.5)
        if not today_supernovas:  # holidays are None, no finds are []
            continue

        for nova in today_supernovas:
            if nova['mover_day_of_action']['percent_change_high'] > 1000:
                print("WARNING: supernova is too big:",
                      nova['mover_day_of_action']['T'], nova['day_of_action'])
                continue
            novas.append(nova)

    return novas


csv_headers = [
    "day_of_action",
    "ticker",
    "is_warrant",
    "percent_change_high",
    "yesterday_close",
    "today_high",
    "yesterday_volume",
    "today_volume"
]


def prepare_supernovas_csv(path: str, start, end):
    novas = get_all_supernovas(
        start, end)

    def yield_supernovas():
        for nova in novas:
            # print(nova)
            # print(nova['mover_day_after'])
            yield {
                "ticker": nova['mover_day_of_action']['T'],
                "is_warrant": is_warrant(nova['mover_day_of_action']['T']),
                "day_of_action": nova['day_of_action'],
                "percent_change_high": nova['mover_day_of_action']['percent_change_high'],
                "yesterday_close": nova['mover_day_of_action']['previous_day_close'],
                "today_high": nova['mover_day_of_action']['h'],
                "yesterday_volume": nova['mover_day_of_action']['previous_day_volume'],
                "today_volume": nova['mover_day_of_action']['v']
            }

    write_csv(path, yield_supernovas(), csv_headers)


def main():
    from src.pathing import get_paths
    path = get_paths()['data']['outputs']["supernovas_csv"]

    start, end = get_cache_prepared_date_range_with_leadup_days(1)

    print("start:", start)
    print("end:", end)
    print("estimated trading days:", len(
        list(generate_trading_days(start, end))))

    prepare_supernovas_csv(path, start, end)


if __name__ == "__main__":
    main()
