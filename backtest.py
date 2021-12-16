from datetime import date, datetime, timedelta
import itertools
from copy import deepcopy

from src.criteria import is_skipped_day, is_warrant


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
        "100sma": float(l["100sma"]) if l["100sma"] else None,

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
        return t["day_of_loss"] > baseline_start_date and not is_skipped_day(t['day_of_loss']) and not is_skipped_day(t['day_after'])

    lines = list(filter(baseline_criteria, lines))

    return lines


def take_top_n_daily(trades, n=10):
    trades_by_day = {}
    for trade in trades:
        key = trade["day_of_loss"].isoformat()
        trades_by_day[key] = trades_by_day.get(key, []) + [trade]

    new_trades = []
    for _day, days_trades in sorted(trades_by_day.items()):
        new_trades.extend(days_trades[:n])

    return new_trades


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
    evaluations_per_second = 1.8e6  # found empirically on my computer

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

        # TODO: refactor this into a function so we can evaluate a criteria set independent of this loop (something exists in hybrid_backtest.py)
        filtered_lines = lines
        for criteria in criterion:
            new_lines = list(filter(criteria, filtered_lines))
            filtered_lines = new_lines

        for n in [8, 10, 12, 15, 20]:

            results = evaluate_results(take_top_n_daily(filtered_lines, n=n))
            if not results:
                continue

            new_criteria_set_descriptor = deepcopy(criteria_set_descriptor)
            new_criteria_set_descriptor["top_n"] = f"top {n}"
            criteria_results.append({
                "names": new_criteria_set_descriptor,
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
        key = line["day_of_loss"].isoformat()
        trades_by_day[key] = trades_by_day.get(key, []) + [line]

    def get_weight(_trade, trades):
        # give each trade a weight of 1/len(trades)
        # (equal weighting of trades each day)
        return 1/len(trades)

    trading_days = 0
    arithmetic_roi = 0

    geometric_balances = {}
    geometric_coefficients = [
        0.33,  # cash account with settling
        .85,
        .95,
        1.0,
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
    rank_day_of_loss = {
        "* rank": lambda _: True,
    }

    def build_rank_criterion(rank):
        def rank_criterion(t):
            return t["rank_day_of_loss"] <= rank
        return rank_criterion

    for i in range(5, 50, 5):
        rank_day_of_loss[f"rank {i}"] = build_rank_criterion(i)

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
        # "rank_day_of_loss": rank_day_of_loss,
        "intraday_percent_change_day_of_loss": intraday_percent_change_day_of_loss,
        "close_to_close_percent_change_day_of_loss": close_to_close_percent_change_day_of_loss,
        "spy_day_of_loss_percent_change": {
            # very red day
            # "<-1%spy": lambda t: t["spy_day_of_loss_percent_change"] < -0.01,
            # "<-.5%spy": lambda t: t["spy_day_of_loss_percent_change"] < -0.005,
            # "spy down": lambda t: t["spy_day_of_loss_percent_change"] < 0,
            # "spy up": lambda t: t["spy_day_of_loss_percent_change"] > 0,
            # not big happy day
            # "<+1%spy": lambda t: t["spy_day_of_loss_percent_change"] < 0.01,
            "* spy": lambda _: True,
        },
        # "dollar_volume_day_of_loss": {
        #     # '$1M vol': lambda t: t["close_day_of_loss"] * t["volume_day_of_loss"] > 1000000,
        #     # '$500k vol': lambda t: t["close_day_of_loss"] * t["volume_day_of_loss"] > 500000,
        #     # '$100k vol': lambda t: t["close_day_of_loss"] * t["volume_day_of_loss"] > 100000,
        #     # '$50k vol': lambda t: t["close_day_of_loss"] * t["volume_day_of_loss"] > 50000,
        #     # NOTE: this has GREAT results, but it would be hard to enter/exit
        #     '* $vol': lambda _: True,
        # },
        # "close_day_of_loss": {
        #     "p < 1": lambda t: t["close_day_of_loss"] < 1,
        #     "p < 3": lambda t: t["close_day_of_loss"] < 3,
        #     "p > 3": lambda t: t["close_day_of_loss"] > 3,
        #     "p < 5": lambda t: t["close_day_of_loss"] < 5,
        #     "p < 10": lambda t: t["close_day_of_loss"] < 10,
        #     "p < 20": lambda t: t["close_day_of_loss"] < 20,
        #     tried a few >, but it was too restrictive
        #     "all $": lambda _: True,
        # },
        "ticker_is_warrant": {
            # "no w": lambda t: not is_warrant(t["ticker"]),
            "only w": lambda t: is_warrant(t["ticker"]),
            # "*w": lambda _: True,
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
    widest_criteria = get_widest_criteria_with_results(pockets)

    baseline_results = widest_criteria["results"]
    print("baseline names", "    ".join(
        sorted(widest_criteria["names"].values())))
    print("baseline results", baseline_results)
    print()

    widest_top_10_criteria = get_widest_criteria_with_results(
        list(filter(lambda p: p["names"]["top_n"] == "top 10", pockets)))
    print("baseline top 10 names", "    ".join(
        sorted(widest_top_10_criteria["names"].values())))
    print("baseline top 10 results", widest_top_10_criteria["results"])
    print()

    key_criteria = "g_85%"
    passing_criterion_sets = list(filter(
        lambda r: r["results"][key_criteria] > baseline_results[key_criteria], pockets))

    show_top = 10
    print(f"subsets which outperform baseline on {key_criteria}:", len(
        passing_criterion_sets))
    best_criteria_sets = sorted(
        passing_criterion_sets, key=lambda c: c["results"][key_criteria], reverse=True)[:show_top]
    for criteria_set in best_criteria_sets:
        print("  ", "  ".join(
            criteria_set["names"].values()).ljust(64), "| " + " ".join(list(map(lambda tup: f"{tup[0]}={round(tup[1], 3)}", criteria_set["results"].items()))))

    return best_criteria_sets


def get_widest_criteria_with_results(pockets):
    widest_criteria = pockets[0]
    for criteria_result in pockets:
        widest_criteria = criteria_result if criteria_result["results"][
            "plays"] > widest_criteria["results"]["plays"] else widest_criteria

    return widest_criteria


if __name__ == "__main__":
    # TODO: test based off of total loss / drawdown

    from src.pathing import get_paths

    path = get_paths()['data']['outputs']["biggest_losers_csv"]
    baseline_start_date = date(2020, 6, 1)

    # try_top_10_with_price_over_3(path, baseline_start_date)

    pockets = analyze_biggest_losers_csv(path, baseline_start_date)
    best_pockets = print_out_interesting_results(pockets)
    best_pocket = best_pockets[0]
    # TODO: get trades of best pocket and look at some more interesting stats
