from datetime import date, datetime, timedelta
import os
import itertools

from cache import read_json_cache, write_json_cache
from criteria import is_skipped_day, is_warrant

HOME = os.environ['HOME']


def get_lines_from_biggest_losers_csv(path, baseline_start_date):
    lines = []
    with open(path, "r") as f:
        lines.extend(f.readlines())

    headers = lines[0].strip().split(",")
    # remove newlines and header row
    lines = [l.strip() for l in lines[1:]]

    # convert to dicts
    raw_dict_lines = [dict(zip(headers, l.strip().split(","))) for l in lines]

    lines = [{
        "day_of_loss": datetime.strptime(l["day_of_loss"], "%Y-%m-%d").date(),
        "day_of_loss_weekday": int(l["day_of_loss_weekday"]),
        "day_of_loss_month": int(l["day_of_loss_month"]),
        "days_overnight": int(l["days_overnight"]),
        "overnight_has_holiday_bool": l["overnight_has_holiday_bool"] == "True",

        "day_after": datetime.strptime(l["day_after"], "%Y-%m-%d").date(),

        "ticker": l["ticker"],

        "open_day_of_loss": float(l["open_day_of_loss"]),
        "close_day_of_loss": float(l["close_day_of_loss"]),
        "high_day_of_loss": float(l["high_day_of_loss"]),
        "low_day_of_loss": float(l["low_day_of_loss"]),
        "volume_day_of_loss": float(l["volume_day_of_loss"]),

        "close_to_close_percent_change_day_of_loss": float(l["close_to_close_percent_change_day_of_loss"]),
        "intraday_percent_change_day_of_loss": float(l["intraday_percent_change_day_of_loss"]),
        "rank_day_of_loss": int(l["rank_day_of_loss"]),

        "14atr": float(l["14atr"]) if l["14atr"] else None,
        "50ema": float(l["50ema"]) if l["50ema"] else None,
        "100ema": float(l["100ema"]) if l["100ema"] else None,

        "spy_day_of_loss_percent_change": float(l["spy_day_of_loss_percent_change"]),
        "spy_day_of_loss_intraday_percent_change": float(l["spy_day_of_loss_intraday_percent_change"]),

        "open_day_after": float(l["open_day_after"]),
        "close_day_after": float(l["close_day_after"]),
        "high_day_after": float(l["high_day_after"]),
        "low_day_after": float(l["low_day_after"]),
        "volume_day_after": float(l["volume_day_after"]),

        "overnight_strategy_roi": float(l["overnight_strategy_roi"]),
        "overnight_strategy_is_win": int(l["overnight_strategy_is_win"]),
    } for l in raw_dict_lines]

    unmapped_fields_in_csv = set(headers) - set(lines[0].keys())
    if unmapped_fields_in_csv:
        print("WARNING update code to include these fields:",
              unmapped_fields_in_csv)
        for unmapped_field in unmapped_fields_in_csv:
            print("\t", unmapped_field, raw_dict_lines[0][unmapped_field])

    def baseline_criteria(t):
        return t["day_of_loss"] > baseline_start_date

    lines = list(filter(baseline_criteria, lines))

    return lines


def try_top_10_with_price_over_3(path, baseline_start_date):
    lines = get_lines_from_biggest_losers_csv(path, baseline_start_date)
    print(lines[0].keys())
    lines = list(
        filter(lambda l: l["close_to_close_percent_change_day_of_loss"] < -.1, lines))
    lines = list(
        filter(lambda l: l["close_day_of_loss"] > 3, lines))
    lines = list(
        filter(lambda l: l["volume_day_of_loss"] > 1000000, lines))
    lines = list(
        filter(lambda l: not is_warrant(l["ticker"]), lines))

    lines.sort(key=lambda t: (t["day_of_loss"],
               t["close_to_close_percent_change_day_of_loss"]))

    def each_day(lines):
        current_day = lines[0]["day_of_loss"]
        lines_for_current_day = []
        for line in lines:
            day = line["day_of_loss"]
            if day != current_day:
                # day has ended
                yield lines_for_current_day
                lines_for_current_day = []
                current_day = day

            lines_for_current_day.append(line)

    for top_n in range(1, 21):
        trades = []
        days_with_insufficient_trades = 0
        for top_losers_of_day in each_day(lines):
            day_of_loss = top_losers_of_day[0]["day_of_loss"]
            day_after = top_losers_of_day[0]["day_after"]

            if is_skipped_day(day_of_loss) or is_skipped_day(day_after):
                continue

            losers_to_trade = top_losers_of_day[:top_n]

            # print(losers_to_trade[0]["day_of_loss"])
            # for loser in losers_to_trade:
            #     print(loser["ticker"], loser["close_to_close_percent_change_day_of_loss"],
            #           loser["rank_day_of_loss"])
            # print()

            if len(losers_to_trade) < top_n:
                days_with_insufficient_trades += 1
                # print(
                #     f"WARNING: not enough losers to trade on, continuing with {len(losers_to_trade)} {top_losers_of_day[0]['day_of_loss']}")

            trades.extend(losers_to_trade)

        # default weighting is equally over all trades in a day
        results = evaluate_results(trades)
        if top_n == 10:
            print()
        print(
            f"top {top_n} ({days_with_insufficient_trades} days not enough)", results)
        if top_n == 10:
            print()


def analyze_biggest_losers_csv(path, baseline_start_date):
    lines = get_lines_from_biggest_losers_csv(path, baseline_start_date)

    criteria_results = []
    criteria_groupings = build_criteria_set()
    criteria_group_names = list(criteria_groupings.keys())
    criteria_groups = list(
        map(lambda name: criteria_groupings[name], criteria_group_names))

    #
    # starting to estimate time
    #
    possible_pockets = 1
    for criteria_group in criteria_groups:
        possible_pockets *= len(criteria_group.items())

    line_count = len(lines)
    evaluations = possible_pockets * line_count
    evaluations_per_second = 2.8e6  # found empirically on my computer

    print("estimated time:", timedelta(
        seconds=evaluations / evaluations_per_second))
    start_time = datetime.now()

    #
    # do lots of work
    #
    for raw_criteria_set in itertools.product(*map(lambda d: d.items(), criteria_groups)):
        criteria_set_names = list(map(lambda t: t[0], raw_criteria_set))
        criteria_set_descriptor = dict(
            zip(criteria_group_names, criteria_set_names))

        criterion = list(map(lambda t: t[1], raw_criteria_set))

        filtered_lines = lines
        for criteria in criterion:
            new_lines = list(filter(criteria, filtered_lines))
            filtered_lines = new_lines

        results = evaluate_results(filtered_lines)
        if not results:
            continue

        criteria_results.append({
            "names": criteria_set_descriptor,
            "results": results,
        })

    end_time = datetime.now()
    print('actual time:', end_time-start_time)

    return criteria_results


def evaluate_results(lines):
    if not lines:
        return None

    plays = len(lines)

    if plays < 10:
        return None

    total_roi = sum(list(map(lambda l: l["overnight_strategy_roi"], lines)))
    average_roi = total_roi / plays

    win_rate = sum(
        list(map(lambda l: 1 if l["overnight_strategy_roi"] > 0 else 0, lines))) / plays

    trades_by_day = {}
    for line in lines:
        key = line["day_of_loss"].strftime("%Y-%m-%d")
        trades_by_day[key] = trades_by_day.get(key, []) + [line]

    def get_weight(trade, trades):
        # give each trade a weight of 1/len(trades)
        # (equal weighting of trades each day)
        return 1/len(trades)

    trading_days = 0
    arithmetic_roi = 0

    geometric_balances = {}
    geometric_coefficients = [
        0.33,  # cash trading
        0.5,  # use half your balance every day
        0.95,  # use most of your balance every day
        1.5,  # use overnight margin
    ]
    for _day, trades in trades_by_day.items():
        trading_days += 1

        today_roi = 0
        for trade in trades:
            today_roi += get_weight(trade, trades) * \
                trade["overnight_strategy_roi"]

        # just take returns, do not reinvest, only withdraw to replenish original capital
        arithmetic_roi += today_roi

        for coefficient in geometric_coefficients:
            balance = geometric_balances.get(coefficient, 1)
            geometric_balances[coefficient] = balance + \
                (today_roi * coefficient * balance)

    # TODO: calculate drawdown and other stats

    results = {
        "a_*": round(arithmetic_roi + 1, 2),
        "avg_roi": round(average_roi, 3),
        "win%": round(win_rate, 3),
        "plays": plays,
        "days": trading_days,
    }

    for coefficient in list(geometric_balances.keys()):
        geometric_balances[coefficient] = round(
            geometric_balances[coefficient], 2)
        results[f"g_{int(100*coefficient)}%"] = geometric_balances[coefficient]

    return results


def build_criteria_set():

    # rank_day_of_loss
    rank_day_of_loss = {}

    def build_rank_criterion(rank):
        def rank_criterion(t):
            return t["rank_day_of_loss"] <= rank
        return rank_criterion

    # top 5
    # top 10
    # top 15
    # top 20 (all)
    for i in [10]:
        # for i in range(1, 21):
        rank_day_of_loss[f"top {i}"] = build_rank_criterion(i)

    # intraday_percent_change_day_of_loss
    intraday_percent_change_day_of_loss = {
        "intr * ": lambda _: True,
    }

    def build_intraday_percent_change_day_of_loss(percent):
        def intraday_percent_change_day_of_loss(t):
            return t["intraday_percent_change_day_of_loss"] < percent
        return intraday_percent_change_day_of_loss

    # intraday loss over -20%
    # intraday loss over -15%
    # intraday loss over -10%
    # intraday loss over -5%
    # intraday loss
    # intraday gain under 5%
    # intraday gain under 10%
    for i in range(-20, 10, 5):
        percent = i / 100
        intraday_percent_change_day_of_loss[f"intr<{i}"] = build_intraday_percent_change_day_of_loss(
            percent)

    # close_to_close_percent_change_day_of_loss
    close_to_close_percent_change_day_of_loss = {
        "change% *": lambda _: True,
    }

    def build_close_to_close_percent_change_day_of_loss(percent):
        def close_to_close_percent_change_day_of_loss(t):
            return t["close_to_close_percent_change_day_of_loss"] < percent
        return close_to_close_percent_change_day_of_loss

    # loss over 50%
    # loss over 45%
    # loss over 40%
    # loss over 35%
    # loss over 30%
    # loss over 25%
    # loss over 20%
    # loss over 15%
    # loss over 10%
    for i in range(-50, -10, 5):
        percent = i / 100
        close_to_close_percent_change_day_of_loss[f"change%<{i}"] = build_close_to_close_percent_change_day_of_loss(
            percent)

    return {
        "rank_day_of_loss": rank_day_of_loss,
        # "intraday_percent_change_day_of_loss": intraday_percent_change_day_of_loss,
        # "close_to_close_percent_change_day_of_loss": close_to_close_percent_change_day_of_loss,
        # "spy_day_of_loss_percent_change": {
        #     # very red day
        #     # "<-1%spy": lambda t: t["spy_day_of_loss_percent_change"] < -0.01,
        #     # "<-.5%spy": lambda t: t["spy_day_of_loss_percent_change"] < -0.005,
        #     "spy down": lambda t: t["spy_day_of_loss_percent_change"] < 0,
        #     # "spy up": lambda t: t["spy_day_of_loss_percent_change"] > 0,
        #     # not big happy day
        #     # "<+1%spy": lambda t: t["spy_day_of_loss_percent_change"] < 0.01,
        #     "* spy": lambda _: True,
        # },
        # "dollar_volume_day_of_loss": {
        #     # '$1M vol': lambda t: t["close_day_of_loss"] * t["volume_day_of_loss"] > 1000000,
        #     # '$500k vol': lambda t: t["close_day_of_loss"] * t["volume_day_of_loss"] > 500000,
        #     # '$100k vol': lambda t: t["close_day_of_loss"] * t["volume_day_of_loss"] > 100000,
        #     # '$50k vol': lambda t: t["close_day_of_loss"] * t["volume_day_of_loss"] > 50000,
        #     # NOTE: this has GREAT results, but it would be hard to enter/exit
        #     '* $vol': lambda _: True,
        # },
        "close_day_of_loss": {
            # "p < 1": lambda t: t["close_day_of_loss"] < 1,
            # "p < 3": lambda t: t["close_day_of_loss"] < 3,
            "p > 3": lambda t: t["close_day_of_loss"] > 3,
            # "p < 5": lambda t: t["close_day_of_loss"] < 5,
            # "p < 10": lambda t: t["close_day_of_loss"] < 10,
            # "p < 20": lambda t: t["close_day_of_loss"] < 20,
            # tried a few >, but it was too restrictive
            # "all $": lambda _: True,
        },
        "ticker_is_warrant": {
            # "no w": lambda t: not is_warrant(t["ticker"]),
            # "only w": lambda t: is_warrant(t["ticker"]),
            "*w": lambda _: True,
        },

        #
        # Days of the week
        #

        # "doulikefriday": {
        #     "! friday": lambda t: t["day_of_loss"].weekday() != 4,
        #     "* friday": lambda _: True,
        # },
        # "doulikethursday": {
        #     "! thursday": lambda t: t["day_of_loss"].weekday() != 3,
        #     "* thursday": lambda _: True,
        # },
        # "doulikewednesday": {
        #     "! wednesday": lambda t: t["day_of_loss"].weekday() != 2,
        #     "* wednesday": lambda _: True,
        # },
        # "douliketuesday": {
        #     "! tuesday": lambda t: t["day_of_loss"].weekday() != 1,
        #     "* tuesday": lambda _: True,
        # },
        # "doulikemonday": {
        #     "! monday": lambda t: t["day_of_loss"].weekday() != 0,
        #     "* monday": lambda _: True,
        # },

        #
        # Quarters of the year
        #

        # "doulikeq1": {
        #     "!q1": lambda t: (t["day_of_loss"].month - 1) // 4 != 0,
        #     "*q1": lambda _: True,
        # },
        # "doulikeq2": {
        #     "!q2": lambda t: (t["day_of_loss"].month - 1) // 4 != 1,
        #     "*q2": lambda _: True,
        # },
        # "doulikeq3": {
        #     "!q3": lambda t: (t["day_of_loss"].month - 1) // 4 != 2,
        #     "*q3": lambda _: True,
        # },
        # "doulikeq4": {
        #     "!q4": lambda t: (t["day_of_loss"].month - 1) // 4 != 3,
        #     "*q4": lambda _: True,
        # },

        #
        # Holidays
        #

        # "is_holiday": {
        #     "! holiday": lambda l: not l["overnight_has_holiday_bool"],
        # ":) holiday": lambda l: l["overnight_has_holiday_bool"],
        # "* holiday": lambda _: True,
        # },

        #
        # EMAs
        #


        # "100ema": {
        #     ">100ema": lambda t: t["100ema"] and t["100ema"] > t["close_day_of_loss"],
        #     # "<100ema": lambda t: t["100ema"] and t["100ema"] < t["close_day_of_loss"],
        #     # "has 100ema": lambda t: t["100ema"] is not None,
        #     "*100ema": lambda _: True,
        # },

        # "50ema": {
        #     ">50ema": lambda t: t["50ema"] and t["50ema"] > t["close_day_of_loss"],
        #     "<50ema": lambda t: t["50ema"] and t["50ema"] < t["close_day_of_loss"],
        #     "has 50ema": lambda t: t["50ema"] is not None,
        #     "*50ema": lambda _: True,
        # },

    }


def print_out_interesting_results(pockets):
    widest_criteria = pockets[0]
    for criteria_result in pockets:
        widest_criteria = criteria_result if criteria_result["results"][
            "plays"] > widest_criteria["results"]["plays"] else widest_criteria

    baseline_results = widest_criteria["results"]
    print("baseline names", "    ".join(
        sorted(widest_criteria["names"].values())))
    print("baseline results", baseline_results)
    print()

    for key_criteria in ["g_roix4"]:
        passing_criterion_sets = list(filter(
            lambda r: r["results"][key_criteria] > baseline_results[key_criteria], pockets))

        show_top = 10
        print(f"subsets which outperform baseline on {key_criteria}:", len(
            passing_criterion_sets))
        for criteria_set in sorted(passing_criterion_sets, key=lambda c: c["results"][key_criteria], reverse=True)[:show_top]:
            print("  ", "  ".join(
                criteria_set["names"].values()).ljust(64), "| " + " ".join(list(map(lambda tup: f"{tup[0]}={round(tup[1], 3)}", criteria_set["results"].items()))))


def get_widest_criteria_with_results(pockets):
    widest_criteria = pockets[0]
    for criteria_result in pockets:
        widest_criteria = criteria_result if criteria_result["results"][
            "plays"] > widest_criteria["results"]["plays"] else widest_criteria

    return widest_criteria


def try_hybrid_model(pockets, path, baseline_start_date, is_quality_pocket):
    quality_pockets = list(filter(is_quality_pocket, pockets))

    lines = get_lines_from_biggest_losers_csv(path, baseline_start_date)

    hybrid_model_trades = []

    criteria_set = build_criteria_set()

    def pocket_includes_line(pocket, line):

        # every criteria must be met
        for dimension_name, segment_name in pocket["names"].items():
            criteria = criteria_set[dimension_name][segment_name]
            if not criteria(line):
                return False

        return True

    for line in lines:
        for pocket in quality_pockets:
            # if any pocket contains the line, then we have a trade
            if pocket_includes_line(pocket, line):
                hybrid_model_trades.append(line)
                break

    results = evaluate_results(hybrid_model_trades)
    if not results:
        return None

    results["hybrid"] = {
        "pockets": len(quality_pockets),
    }

    return results, quality_pockets


def build_pocket_quality_criteria(min_plays=None, min_avg_roi=None, min_win_percent=None, min_g_roi=None, min_a_roi=None):
    criterion = []

    if min_plays:
        criterion.append(
            lambda pocket: pocket["results"]["plays"] >= min_plays)

    if min_avg_roi:
        criterion.append(
            lambda pocket: pocket["results"]["avg_roi"] >= min_avg_roi)

    if min_win_percent:
        criterion.append(
            lambda pocket: pocket["results"]["win%"] >= min_win_percent)

    if min_g_roi:
        criterion.append(
            lambda pocket: pocket["results"]["g_roi"] >= min_g_roi)

    if min_a_roi:
        criterion.append(
            lambda pocket: pocket["results"]["a_roi"] >= min_a_roi)

    def is_quality_pocket(pocket):
        return all((
            criteria(pocket)
            for criteria in criterion
        ))

    return is_quality_pocket


if __name__ == "__main__":
    # TODO: test based off of total loss / drawdown

    path = f"{HOME}/biggest_losers.csv"
    baseline_start_date = date(2021, 1, 1)

    try_top_10_with_price_over_3(path, baseline_start_date)
    exit(0)

    write_new_model = True
    model_cache_entry = "modelv2"

    if write_new_model:
        pockets = analyze_biggest_losers_csv(
            path, baseline_start_date)
        write_json_cache(model_cache_entry, pockets)
    else:
        pockets = read_json_cache(model_cache_entry)

    print()
    print_out_interesting_results(pockets)
    print()
    print("-" * 80)
    baseline_results = get_widest_criteria_with_results(pockets)["results"]
    print(f"baseline with {len(pockets)} pockets", baseline_results)
    print()

    is_quality_pocket = build_pocket_quality_criteria(
        min_win_percent=.5, min_avg_roi=.05, min_plays=30)

    # TODO: try a hybrid model if pockets are non-overlapping and then use quality + min pocket criteria

    hybrid_results_pockets = try_hybrid_model(
        pockets, path, baseline_start_date, is_quality_pocket)
    if not hybrid_results_pockets:
        print("no hybrid model")
        exit(1)
    results, pockets = hybrid_results_pockets

    for pocket in pockets:
        print("  ", "  ".join(
            pocket["names"].values()).ljust(64), "| " + " ".join(list(map(lambda tup: f"{tup[0]}={round(tup[1], 3)}", pocket["results"].items()))))

    print()
    print("hybrid", results)
