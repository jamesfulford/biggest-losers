from datetime import date
from src.criteria import is_warrant
from src.csv_dump import write_csv
from src.grouped_aggs import get_cache_prepared_date_range_with_leadup_days
from src.gappers import get_gappers
from src.trading_day import generate_trading_days


def get_all_gappers_between(start: date, end: date):
    gappers = []
    for day in generate_trading_days(start, end):
        today_gappers = get_gappers(day)
        if not today_gappers:  # holidays
            continue
        for gapper in today_gappers:
            gappers.append(gapper)
    return gappers


def prepare_biggest_winners_csv(path: str, start: date, end: date):
    biggest_movers = get_all_gappers_between(start, end)

    def yield_movers():
        for mover in biggest_movers:
            day_of_action = mover["day_of_action"]
            mover_day_of_action = mover["mover_day_of_action"]
            mover_day_before = mover["mover_day_before"]

            yield {
                "day_of_action": day_of_action,
                "ticker": mover_day_of_action['T'],
                "is_warrant": is_warrant(mover_day_of_action['T']),

                # day_of_action stats
                "open_day_of_action": mover_day_of_action['o'],
                "high_day_of_action": mover_day_of_action['h'],
                "low_day_of_action": mover_day_of_action['l'],
                "close_day_of_action": mover_day_of_action['c'],
                "volume_day_of_action": mover_day_of_action['v'],

                # previous day stats
                "open_day_before": mover_day_before['o'],
                "high_day_before": mover_day_before['h'],
                "low_day_before": mover_day_before['l'],
                "close_day_before": mover_day_before['c'],
                "volume_day_before": mover_day_before['v'],

                "gap_close_to_open_percent_change_day_of_action": (mover_day_of_action['o'] - mover_day_before['c']) / mover_day_before['c'],
                "close_to_close_percent_change_day_of_action": (mover_day_of_action['c'] - mover_day_before['c']) / mover_day_before['c'],
                "intraday_open_to_close_percent_change_day_of_action": (mover_day_of_action['c'] -
                                                                        mover_day_of_action['o']) / mover_day_of_action['o'],
                "open_to_high_percent_change_day_of_action": (mover_day_of_action['h'] -
                                                              mover_day_of_action['o']) / mover_day_of_action['o'],
                "open_to_low_percent_change_day_of_action": (mover_day_of_action['l'] -
                                                             mover_day_of_action['o']) / mover_day_of_action['o'],

                "rank_day_of_action": mover_day_of_action.get("rank", -1),

                # day of loss indicators
                # "100sma": mover.get("100sma", ""),
                # "100ema": mover.get("100ema", ""),
                # "50ema": mover.get("50ema", ""),
                # "14atr": mover.get("14atr", ""),

                # day_after stats
                # TODO: add, wonder if anything happens
                # "open_day_after": mover_day_after['o'],
                # "high_day_after": mover_day_after['h'],
                # "low_day_after": mover_day_after['l'],
                # "close_day_after": mover_day_after['c'],
                # "volume_day_after": mover_day_after['v'],

                # spy
                # TODO: do enriching in this script instead of other file?
                # "spy_day_of_action_percent_change": spy_day_of_action_percent_change,
                # "spy_day_of_action_intraday_percent_change": spy_day_of_action_intraday_percent_change,

                # results
                # "overnight_strategy_roi": overnight_strategy_roi,
                # "overnight_strategy_is_win": overnight_strategy_roi > 0,
            }

    write_csv(path, yield_movers(), headers=[
        "day_of_action",
        "ticker",
        "is_warrant",
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
        #
        "gap_close_to_open_percent_change_day_of_action",
        "close_to_close_percent_change_day_of_action",
        "intraday_open_to_close_percent_change_day_of_action",
        "open_to_high_percent_change_day_of_action",
        "open_to_low_percent_change_day_of_action",
        "rank_day_of_action",
    ])


def main():
    from src.pathing import get_paths
    path = get_paths()['data']['outputs']["gappers_csv"]

    # need at least 100 trading days for 100 EMA to compute
    # TODO: if not 100 days available, make column blank so we can have more rows
    start, end = get_cache_prepared_date_range_with_leadup_days(1)

    print("start:", start)
    print("end:", end)
    print("estimated trading days:", len(
        list(generate_trading_days(start, end))))

    prepare_biggest_winners_csv(path, start, end)


if __name__ == "__main__":
    main()
