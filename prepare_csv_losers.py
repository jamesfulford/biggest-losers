from datetime import date
import os

from src.mover_enrichers import enrich_mover
from src.movers import collect_overnights
from src.losers import get_biggest_losers
from src.trading_day import previous_trading_day


def get_all_biggest_losers_with_day_after(start_date: date, end_date: date):
    movers = []
    for mover in collect_overnights(
            start_date, end_date, get_actions_on_day=lambda day: get_biggest_losers(day, top_n=1000)):
        enrich_mover(mover)
        movers.append(mover)
    return movers


# keep in sync with usage of write_csv
csv_headers = [
    # TODO: replace with "day_of_action" and update downstream scripts
    "day_of_loss",
    "day_of_loss_weekday",
    "day_of_loss_month",
    "day_after",
    "days_overnight",
    "overnight_has_holiday_bool",
    "ticker",
    #
    "open_day_of_loss",
    "high_day_of_loss",
    "low_day_of_loss",
    "close_day_of_loss",
    "volume_day_of_loss",
    #
    "close_to_close_percent_change_day_of_loss",
    "intraday_percent_change_day_of_loss",
    "rank_day_of_loss",
    #
    "100sma",
    "100ema",
    "50ema",
    "14atr",
    #
    "open_day_after",
    "high_day_after",
    "low_day_after",
    "close_day_after",
    "volume_day_after",
    #
    "spy_day_of_loss_percent_change",
    "spy_day_of_loss_intraday_percent_change",
    #
    "overnight_strategy_roi",
    "overnight_strategy_is_win",
]


def prepare_biggest_losers_csv(path, start_date, end_date):
    biggest_movers = get_all_biggest_losers_with_day_after(
        start_date, end_date)

    # TODO: use shared csv writer to make this simpler, less error-prone

    try:
        os.remove(path)
    except:
        pass

    with open(path, "a") as f:
        def write_to_csv(line):
            f.write(line + "\n")

        write_to_csv(",".join(csv_headers))

        for mover in biggest_movers:
            day_of_action = mover["day_of_action"]
            day_after = mover["day_after"]
            mover_day_of_action = mover["mover_day_of_action"]
            mover_day_after = mover["mover_day_after"]
            spy_day_of_action_percent_change = mover["spy_day_of_action_percent_change"]
            spy_day_of_action_intraday_percent_change = mover[
                "spy_day_of_action_intraday_percent_change"]

            intraday_percent_change = (mover_day_of_action['c'] -
                                       mover_day_of_action['o']) / mover_day_of_action['o']

            overnight_strategy_roi = (
                mover_day_after['o'] - mover_day_of_action['c']) / mover_day_of_action['c']

            # keep in sync with headers
            write_to_csv(",".join(list(map(str, [
                day_of_action.strftime("%Y-%m-%d"),
                day_of_action.weekday(),
                day_of_action.month,
                day_after.strftime("%Y-%m-%d"),
                (day_after - day_of_action).days,
                previous_trading_day(day_after) != day_of_action,
                mover_day_of_action['T'],
                # day_of_action stats
                mover_day_of_action['o'],
                mover_day_of_action['h'],
                mover_day_of_action['l'],
                mover_day_of_action['c'],
                mover_day_of_action['v'],
                mover_day_of_action["percent_change"],
                intraday_percent_change,
                mover_day_of_action.get("rank", -1),
                # day of loss indicators
                mover.get("100sma", ""),
                mover.get("100ema", ""),
                mover.get("50ema", ""),
                mover.get("14atr", ""),
                # day_after stats
                mover_day_after['o'],
                mover_day_after['h'],
                mover_day_after['l'],
                mover_day_after['c'],
                mover_day_after['v'],
                # spy
                spy_day_of_action_percent_change,
                spy_day_of_action_intraday_percent_change,
                # results
                overnight_strategy_roi,
                1 if overnight_strategy_roi > 0 else 0,
            ]))))


def main():
    from src.pathing import get_paths
    path = get_paths()['data']['outputs']["biggest_losers_csv"]

    # earliest date I have data for on my machine
    # start_date = date(2019, 11, 18)
    # (but need more time because of 100smas)

    start_date = date(2020, 6, 1)
    end_date = date.today()
    prepare_biggest_losers_csv(path, start_date=start_date, end_date=end_date)


if __name__ == "__main__":
    main()
