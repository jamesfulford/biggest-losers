from datetime import date
from src.csv_dump import write_csv
from src.grouped_aggs import get_cache_prepared_date_range_with_leadup_days

from src.mover_enrichers import enrich_mover
from src.overnights import collect_overnights
from src.scan.winners import get_biggest_winners
from src.trading_day import generate_trading_days, previous_trading_day


def get_all_biggest_winners_with_day_after(start_date: date, end_date: date):
    movers = []
    for mover in collect_overnights(
        start_date, end_date, get_actions_on_day=lambda day: get_biggest_winners(
            day)
    ):
        enrich_mover(mover)
        movers.append(mover)
    return movers


def prepare_biggest_winners_csv(path: str, start, end):
    biggest_movers = get_all_biggest_winners_with_day_after(start, end)

    def yield_movers():
        for mover in biggest_movers:
            day_of_action = mover["day_of_action"]
            day_after = mover["day_after"]
            mover_day_of_action = mover["mover_day_of_action"]
            mover_day_after = mover["mover_day_after"]
            spy_day_of_action_percent_change = mover["spy_day_of_action_percent_change"]
            spy_day_of_action_intraday_percent_change = mover[
                "spy_day_of_action_intraday_percent_change"
            ]

            intraday_percent_change = (
                mover_day_of_action["c"] - mover_day_of_action["o"]
            ) / mover_day_of_action["o"]

            overnight_strategy_roi = (
                mover_day_after["o"] - mover_day_of_action["c"]
            ) / mover_day_of_action["c"]

            # keep in sync with headers
            yield {
                "day_of_action": day_of_action,
                "day_of_action_weekday": day_of_action.weekday(),
                "day_of_action_month": day_of_action.month,
                "day_after": day_after,
                "days_overnight": (day_after - day_of_action).days,
                "overnight_has_holiday_bool": previous_trading_day(day_after)
                != day_of_action,
                "ticker": mover_day_of_action["T"],
                # day_of_action stats
                "open_day_of_action": mover_day_of_action["o"],
                "high_day_of_action": mover_day_of_action["h"],
                "low_day_of_action": mover_day_of_action["l"],
                "close_day_of_action": mover_day_of_action["c"],
                "volume_day_of_action": mover_day_of_action["v"],
                "close_to_close_percent_change_day_of_action": mover_day_of_action[
                    "percent_change"
                ],
                "intraday_percent_change_day_of_action": intraday_percent_change,
                "rank_day_of_action": mover_day_of_action.get("rank", -1),
                # day of loss indicators
                "100sma": mover.get("100sma", ""),
                "100ema": mover.get("100ema", ""),
                "50ema": mover.get("50ema", ""),
                "14atr": mover.get("14atr", ""),
                # day_after stats
                "open_day_after": mover_day_after["o"],
                "high_day_after": mover_day_after["h"],
                "low_day_after": mover_day_after["l"],
                "close_day_after": mover_day_after["c"],
                "volume_day_after": mover_day_after["v"],
                # spy
                "spy_day_of_action_percent_change": spy_day_of_action_percent_change,
                "spy_day_of_action_intraday_percent_change": spy_day_of_action_intraday_percent_change,
                # results
                "overnight_strategy_roi": overnight_strategy_roi,
                "overnight_strategy_is_win": overnight_strategy_roi > 0,
            }

    write_csv(
        path,
        yield_movers(),
        headers=[
            "day_of_action",
            "day_of_action_weekday",
            "day_of_action_month",
            "day_after",
            "days_overnight",
            "overnight_has_holiday_bool",
            "ticker",
            #
            "open_day_of_action",
            "high_day_of_action",
            "low_day_of_action",
            "close_day_of_action",
            "volume_day_of_action",
            #
            "close_to_close_percent_change_day_of_action",
            "intraday_percent_change_day_of_action",
            "rank_day_of_action",
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
            "spy_day_of_action_percent_change",
            "spy_day_of_action_intraday_percent_change",
            #
            "overnight_strategy_roi",
            "overnight_strategy_is_win",
        ],
    )


def main():
    from src.pathing import get_paths

    path = get_paths()["data"]["outputs"]["biggest_winners_csv"]

    start, end = get_cache_prepared_date_range_with_leadup_days(1)

    print("start:", start)
    print("end:", end)
    print("estimated trading days:", len(
        list(generate_trading_days(start, end))))

    prepare_biggest_winners_csv(path, start, end)


if __name__ == "__main__":
    main()
