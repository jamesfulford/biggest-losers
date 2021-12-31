from datetime import date
import os

from src.mover_enrichers import enrich_mover
from src.movers import collect_overnights
from src.supernovas import get_supernovas
from src.trading_day import previous_trading_day
from src.csv_dump import write_csv


def get_all_supernovas(start_date: date, end_date: date):
    novas = []
    for nova in collect_overnights(
            start_date, end_date, get_actions_on_day=lambda day: get_supernovas(day, pct=2)):
        # enrich_mover(nova)
        novas.append(nova)
    return novas


# keep in sync with usage of write_csv
csv_headers = [
    "ticker",
    "day_of_action",
    "percent_change_high",
    "yesterday_close",
    "today_high",
    "yesterday_volume",
    "today_volume"
]


def prepare_supernovas_csv(path, start_date, end_date):
    novas = get_all_supernovas(
        start_date, end_date)

    try:
        os.remove(path)
    except:
        pass

    def yield_supernovas():
        for nova in novas:
            print(nova)
            # print(nova['mover_day_after'])
            yield {
                "ticker": nova['mover_day_of_action']['T'],
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

    # earliest date I have data for on my machine
    # start_date = date(2019, 11, 18)
    # (but need more time because of 100smas)

    start_date = date(2020, 6, 1)
    end_date = date(2021, 12, 30)
    prepare_supernovas_csv(path, start_date=start_date, end_date=end_date)


if __name__ == "__main__":
    main()
