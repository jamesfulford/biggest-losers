from datetime import date, datetime, timedelta
from src.csv_dump import write_csv
from src.finnhub import extract_intraday_candle_at_or_after_time, get_candles
from src.grouped_aggs import get_cache_prepared_date_range_with_leadup_days

from src.mover_enrichers import enrich_mover
from src.overnights import collect_overnights
from src.losers import get_biggest_losers
from src.trading_day import (
    generate_trading_days,
    get_market_close_on_day,
    get_market_open_on_day,
    previous_trading_day,
)
from src.criteria import is_stock, is_warrant


def get_all_biggest_losers_with_day_after(start_date: date, end_date: date):
    for mover in collect_overnights(
        start_date, end_date, get_actions_on_day=lambda day: get_biggest_losers(day)
    ):
        enrich_mover(mover)
        yield mover


def enrich_mover_with_day_after_intraday_exits(mover):
    ticker = mover["mover_day_of_action"]["T"]
    day_of_action = mover["day_of_action"]
    day_after = mover["day_after"]

    # finnhub intraday is unadjusted, cannot compare to other columns!
    # however, ROI %'s can be compared
    candles = get_candles(ticker, "1", day_of_action, day_after)
    if not candles:
        return

    # TODO: add some bracketing logic columns
    # TODO: add time of high of day for day_after (better exit)
    # TODO: add time of low of day for day_of_action (better entry?)
    # TODO: add some fixed times for entry for day_of_action

    candle_day_of_action_close = extract_intraday_candle_at_or_after_time(
        candles, get_market_close_on_day(day_of_action) - timedelta(minutes=1)
    )
    entry_price_finnhub = candle_day_of_action_close["close"]
    market_open_day_after = get_market_open_on_day(day_after)

    for fixed_exit_time in [
        {
            "time_after_open": timedelta(minutes=0),
            "roi_name": "fn_close_to_09_30_roi",
        },
        {
            "time_after_open": timedelta(minutes=30),
            "roi_name": "fn_close_to_10_00_roi",
        },
    ]:
        candle = extract_intraday_candle_at_or_after_time(
            candles, market_open_day_after + fixed_exit_time["time_after_open"]
        )
        if not candle:
            continue
        mover[fixed_exit_time["roi_name"]] = (
            candle["open"] - entry_price_finnhub
        ) / entry_price_finnhub


def prepare_biggest_losers_csv(path: str, start: date, end: date):
    def yield_biggest_losers():
        for mover in get_all_biggest_losers_with_day_after(start, end):
            day_of_action = mover["day_of_action"]
            day_after = mover["day_after"]
            mover_day_of_action = mover["mover_day_of_action"]
            mover_day_after = mover["mover_day_after"]

            symbol = mover_day_of_action["T"]

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

            if (
                is_stock(symbol)
                and (day_of_action > date.today() - timedelta(days=365))
                and mover_day_of_action["v"] > 100000
            ):
                # triggers finnhub requests, so want to do less often
                # also fails for warrants, units, and some other non-common-stock tickers,
                # so filtering those out too so we waste less rate limit quota
                enrich_mover_with_day_after_intraday_exits(mover)

            yield {
                "day_of_action": day_of_action,
                "day_of_action_weekday": day_of_action.weekday(),
                "day_of_action_month": day_of_action.month,
                "day_after": day_after,
                "days_overnight": (day_after - day_of_action).days,
                "overnight_has_holiday_bool": previous_trading_day(day_after)
                != day_of_action,
                "ticker": symbol,
                "is_warrant": is_warrant(symbol),
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
                "fn_close_to_09_30_roi": mover.get("fn_close_to_09_30_roi"),
                "fn_close_to_10_00_roi": mover.get("fn_close_to_10_00_roi"),
            }

    write_csv(
        path,
        yield_biggest_losers(),
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

    path = get_paths()["data"]["outputs"]["biggest_losers_csv"]

    start, end = get_cache_prepared_date_range_with_leadup_days(1)

    print("start:", start)
    print("end:", end)
    print("estimated trading days:", len(list(generate_trading_days(start, end))))

    prepare_biggest_losers_csv(path, start=start, end=end)


if __name__ == "__main__":
    main()
