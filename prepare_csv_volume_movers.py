from datetime import date
from src.overnights import collect_overnights
from src.scan.volume_movers import get_volume_movers
from src.criteria import is_etf, is_right, is_stock, is_unit, is_warrant
from src.csv_dump import write_csv
from src.grouped_aggs import get_cache_prepared_date_range_with_leadup_days
from src.trading_day import generate_trading_days


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


def main():
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


if __name__ == "__main__":
    main()
