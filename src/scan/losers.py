from datetime import date, timedelta
from src.criteria import is_etf, is_right, is_stock, is_unit, is_warrant
from src.trading_day import (
    generate_trading_days,
    get_market_close_on_day,
    get_market_open_on_day,
    previous_trading_day,
)
from src.overnights import collect_overnights
from src.mover_enrichers import enrich_mover
from src.grouped_aggs import get_cache_prepared_date_range_with_leadup_days
from src.get_candles import extract_intraday_candle_at_or_after_time, get_candles
from src.csv_dump import write_csv
from src.grouped_aggs import get_today_grouped_aggs, get_last_trading_day_grouped_aggs


def get_biggest_losers(today, max_percent_change=-.08, skip_cache=False):
    today_grouped_aggs = get_today_grouped_aggs(today, skip_cache=skip_cache)
    if not today_grouped_aggs:
        print(f'no data for {today}, cannot fetch biggest losers')
        return None
    yesterday_grouped_aggs = get_last_trading_day_grouped_aggs(today)

    #
    # go find biggest losers for the next day
    #

    # skip if wasn't present yesterday
    tickers_also_present_yesterday = list(filter(
        lambda t: t['T'] in yesterday_grouped_aggs['tickermap'], today_grouped_aggs['results']))

    for ticker in tickers_also_present_yesterday:
        previous_day_ticker = yesterday_grouped_aggs['tickermap'][ticker['T']]

        ticker['percent_change'] = (
            ticker['c'] - previous_day_ticker['c']) / previous_day_ticker['c']

    # has to lose at least 8% (default)
    biggest_losers = list(
        filter(lambda t: t['percent_change'] < max_percent_change, tickers_also_present_yesterday))

    biggest_losers = sorted(biggest_losers,
                            key=lambda t: t['percent_change'])
    for loser in biggest_losers:
        loser['rank'] = biggest_losers.index(loser) + 1

    return biggest_losers


def get_all_biggest_losers_with_day_after(start_date: date, end_date: date):
    for mover in collect_overnights(
        start_date, end_date, get_actions_on_day=lambda day: get_biggest_losers(
            day)
    ):
        enrich_mover(mover)
        yield mover


def enrich_mover_with_day_after_intraday_exits(mover):
    ticker = mover["mover_day_of_action"]["T"]
    day_of_action = mover["day_of_action"]
    day_after = mover["day_after"]

    # These candles are adjusted, but may be adjusted differently
    # than grouped_aggs because fetched at different times.
    candles = get_candles(ticker, "1", day_of_action, day_after)
    if not candles:
        return

    # TODO: add some bracketing logic columns
    # TODO: add time of high of day for day_after (better exit)
    # TODO: add time of low of day for day_of_action (better entry?)

    candle_day_after_open = extract_intraday_candle_at_or_after_time(
        candles, get_market_open_on_day(day_after)
    )
    exit_price_intraday = candle_day_after_open["open"]
    market_close_day_of_action = get_market_close_on_day(day_of_action)

    for fixed_entry_time in [
        {
            "time_before_close": timedelta(minutes=1),
            "roi_name": "15_59_to_open_roi",
        },
        {
            "time_before_close": timedelta(minutes=15),
            "roi_name": "15_45_to_open_roi",
        },
    ]:
        candle = extract_intraday_candle_at_or_after_time(
            candles, market_close_day_of_action -
            fixed_entry_time["time_before_close"]
        )
        if not candle:
            continue
        mover[fixed_entry_time["roi_name"]] = (
            exit_price_intraday - candle["open"]
        ) / candle["open"]

    candle_day_of_action_close = extract_intraday_candle_at_or_after_time(
        candles, get_market_close_on_day(day_of_action) - timedelta(minutes=1)
    )
    entry_price_intraday = candle_day_of_action_close["close"]
    market_open_day_after = get_market_open_on_day(day_after)

    for fixed_exit_time in [
        {
            "time_after_open": timedelta(minutes=0),
            "roi_name": "close_to_09_30_roi",
        },
        {
            "time_after_open": timedelta(minutes=30),
            "roi_name": "close_to_10_00_roi",
        },
    ]:
        candle = extract_intraday_candle_at_or_after_time(
            candles, market_open_day_after + fixed_exit_time["time_after_open"]
        )
        if not candle:
            continue
        mover[fixed_exit_time["roi_name"]] = (
            candle["open"] - entry_price_intraday
        ) / entry_price_intraday


def enhance_mover(mover):
    day_of_action = mover["day_of_action"]
    day_after = mover["day_after"]
    mover_day_of_action = mover["mover_day_of_action"]
    mover_day_after = mover["mover_day_after"]

    symbol = mover_day_of_action["T"]

    t_is_stock = is_stock(symbol, day=day_of_action)
    t_is_etf = is_etf(symbol, day=day_of_action)
    t_is_warrant = is_warrant(symbol, day=day_of_action)
    t_is_unit = is_unit(symbol, day=day_of_action)
    t_is_right = is_right(symbol, day=day_of_action)

    if not any((t_is_stock, t_is_etf, t_is_warrant, t_is_unit, t_is_right)):
        # print(f"Ignoring {symbol}")
        return

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

    return {
        "day_of_action": day_of_action,
        "day_of_action_weekday": day_of_action.weekday(),
        "day_of_action_month": day_of_action.month,
        "day_after": day_after,
        "days_overnight": (day_after - day_of_action).days,
        "overnight_has_holiday_bool": previous_trading_day(day_after) != day_of_action,

        # ticker insights
        "ticker": symbol,
        "is_stock": t_is_stock,
        "is_etf": t_is_etf,
        "is_warrant": t_is_warrant,
        "is_unit": t_is_unit,
        "is_right": t_is_right,

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
        "close_to_09_30_roi": mover.get("close_to_09_30_roi"),
        "close_to_10_00_roi": mover.get("close_to_10_00_roi"),
        "15_59_to_open_roi": mover.get("15_59_to_open_roi"),
        "15_45_to_open_roi": mover.get("15_45_to_open_roi"),
    }


def prepare_biggest_losers_csv(path: str, start: date, end: date):
    def yield_biggest_losers():
        current_day = None
        current_days_movers = []
        for mover in get_all_biggest_losers_with_day_after(start, end):
            if not current_day:
                current_day = mover["day_of_action"]

            if current_day != mover["day_of_action"]:

                # selectively enrich
                if current_day.year == 2021:
                    # ARBITRARY DECISION ALERT:
                    # only enriching movers that:
                    # 1. have stock-like tickers (not warrants, rights, units, etc.)
                    # 2. have a volume > 500k
                    # 3. then only the first 10 of those on each day
                    movers_to_enrich = list(
                        filter(
                            lambda m: is_stock(
                                m["mover_day_of_action"]["T"], day=m["day_of_action"]),
                            current_days_movers,
                        )
                    )
                    movers_to_enrich = list(
                        filter(
                            lambda m: m["mover_day_of_action"]["v"] > 500000,
                            movers_to_enrich,
                        )
                    )
                    movers_to_enrich = list(
                        filter(
                            lambda m: m["mover_day_of_action"]["c"] < 2,
                            movers_to_enrich,
                        )
                    )
                    movers_to_enrich = movers_to_enrich[:10]
                    print(
                        current_day,
                        f"(days left: {(end - current_day).days}):",
                        "enriching",
                        list(
                            map(
                                lambda m: m["mover_day_of_action"]["T"],
                                movers_to_enrich,
                            )
                        ),
                    )
                    for m in movers_to_enrich:
                        # has side effects on m
                        enrich_mover_with_day_after_intraday_exits(m)

                for m in current_days_movers:
                    enhanced_m = enhance_mover(m)
                    if enhanced_m:
                        yield enhanced_m

                current_day = mover["day_of_action"]
                current_days_movers = []

            current_days_movers.append(mover)

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


def prepare_csv():
    from src.pathing import get_paths

    path = get_paths()["data"]["outputs"]["biggest_losers_csv"]

    start, end = get_cache_prepared_date_range_with_leadup_days(1)
    start = max(start, date(2021, 1, 1))

    print("start:", start)
    print("end:", end)
    print("estimated trading days:", len(
        list(generate_trading_days(start, end))))

    prepare_biggest_losers_csv(path, start=start, end=end)
