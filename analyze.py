from datetime import date, datetime, timedelta
import os
import itertools

from cache import read_json_cache, write_json_cache

HOME = os.environ['HOME']


def is_warrant(t):
    return (t["ticker"].upper().endswith("W") or ".WS" in t["ticker"].upper())


def get_lines_from_biggest_losers_csv(path):
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

    return lines


def analyze_biggest_losers_csv(path):
    lines = get_lines_from_biggest_losers_csv(path)

    baseline_start_date = date.today() - timedelta(weeks=52)

    def baseline_criteria(t):
        return t["day_of_loss"] > baseline_start_date

    lines = list(filter(baseline_criteria, lines))

    # TODO: test based off of total loss
    # TODO: change spreadsheet source to get even more losers, maybe just penny stock with enough volume

    print('going through criteria')
    criteria_results = []
    criteria_groupings = build_criteria_set()
    criteria_group_names = list(criteria_groupings.keys())
    criteria_groups = list(
        map(lambda name: criteria_groupings[name], criteria_group_names))
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
    print('done going through criteria')

    write_json_cache("modelv0", criteria_results)


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
    geometric_current_balance = 1
    for _day, trades in trades_by_day.items():
        trading_days += 1

        today_roi = 0
        for trade in trades:
            today_roi += get_weight(trade, trades) * \
                trade["overnight_strategy_roi"]

        # just take returns, do not reinvest, only withdraw to replenish original capital
        arithmetic_roi += today_roi

        # reinvest returns, every day invest 1/3 of balance (cash account)
        geometric_current_balance = (
            1/3) * geometric_current_balance * (1 + today_roi) + (2/3) * geometric_current_balance

    # TODO: calculate drawdown and other stats

    return {
        "a_roi": arithmetic_roi,
        "g_roi": geometric_current_balance - 1,
        "plays": plays,
        "avg_roi": average_roi,
        "win%": win_rate,
        "days": trading_days,
    }


def build_criteria_set():

    # rank_day_of_loss
    rank_day_of_loss = {
        "all rank": lambda _: True,
    }

    def build_rank_criterion(rank):
        def rank_criterion(t):
            return t["rank_day_of_loss"] <= rank
        return rank_criterion

    for i in range(5, 21, 5):
        rank_day_of_loss[f"top {i}"] = build_rank_criterion(i)

    # intraday_percent_change_day_of_loss
    intraday_percent_change_day_of_loss = {
        "intr * ": lambda _: True,
    }

    def build_intraday_percent_change_day_of_loss(percent):
        def intraday_percent_change_day_of_loss(t):
            return t["intraday_percent_change_day_of_loss"] < percent
        return intraday_percent_change_day_of_loss

    for i in range(-20, 10, 5):
        percent = i / 100
        intraday_percent_change_day_of_loss[f"intr<{i}"] = build_intraday_percent_change_day_of_loss(
            percent)

    return {
        "rank_day_of_loss": rank_day_of_loss, "intraday_percent_change_day_of_loss": intraday_percent_change_day_of_loss,
        "spy_day_of_loss_percent_change": {
            # "<-1%spy": lambda t: t["spy_day_of_loss_percent_change"] < -0.01,  # very red day
            # not big happy day
            # "<+1%spy": lambda t: t["spy_day_of_loss_percent_change"] < 0.01,
            "* spy": lambda _: True,
        }, "dollar_volume_day_of_loss": {
            # '$1M vol': lambda t: t["close_day_of_loss"] * t["volume_day_of_loss"] > 1000000,
            # '$100k vol': lambda t: t["close_day_of_loss"] * t["volume_day_of_loss"] > 100000,
            '$50k vol': lambda t: t["close_day_of_loss"] * t["volume_day_of_loss"] > 50000,
            # NOTE: this has GREAT results, but it would be hard to enter/exit
            # '* $vol': lambda _: True,
        }, "close_day_of_loss": {
            "p < 1": lambda t: t["close_day_of_loss"] < 1,
            "p < 3": lambda t: t["close_day_of_loss"] < 3,
            "p < 5": lambda t: t["close_day_of_loss"] < 5,
            # "p < 10": lambda t: t["close_day_of_loss"] < 10,
            # "p < 20": lambda t: t["close_day_of_loss"] < 20,
            # tried a few >, but it was too restrictive
            "all $": lambda _: True,
        },
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

        "doulikeq1": {
            "!q1": lambda t: (t["day_of_loss"].month - 1) // 4 != 0,
            "*q1": lambda _: True,
        },
        "doulikeq2": {
            "!q2": lambda t: (t["day_of_loss"].month - 1) // 4 != 1,
            "*q2": lambda _: True,
        },
        "doulikeq3": {
            "!q3": lambda t: (t["day_of_loss"].month - 1) // 4 != 2,
            "*q3": lambda _: True,
        },
        "doulikeq4": {
            "!q4": lambda t: (t["day_of_loss"].month - 1) // 4 != 3,
            "*q4": lambda _: True,
        },

        "ticker_is_warrant": {
            # "no w": lambda t: not is_warrant(t),
            "only w": lambda t: is_warrant(t),
            # "*w": lambda _: True,
        },
    }


def print_out_interesting_results():
    criteria_results = read_json_cache("modelv0")

    widest_criteria = criteria_results[0]
    for criteria_result in criteria_results:
        widest_criteria = criteria_result if criteria_result["results"][
            "plays"] > widest_criteria["results"]["plays"] else widest_criteria

    baseline_results = widest_criteria["results"]
    print("baseline", baseline_results)
    print()

    for key_criteria in ["a_roi", "g_roi"]:
        passing_criterion_sets = list(filter(
            lambda r: r["results"][key_criteria] > baseline_results[key_criteria], criteria_results))

        # minimum_percent_plays = 0
        # passing_criterion_sets = list(filter(
        #     lambda r: r["results"]["plays"] > minimum_percent_plays * baseline_results["plays"], passing_criterion_sets))

        # minimum_trading_days_percent = 0
        # passing_criterion_sets = list(filter(
        #     lambda r: r["results"]["days"] > minimum_trading_days_percent * baseline_results["days"], passing_criterion_sets))

        show_top = 3
        print(f"subsets which outperform baseline on {key_criteria}:", len(
            passing_criterion_sets))
        for criteria_set in sorted(passing_criterion_sets, key=lambda c: c["results"][key_criteria], reverse=True)[:show_top]:
            print("  ", "  ".join(
                criteria_set["names"].values()).ljust(64), "| " + " ".join(list(map(lambda tup: f"{tup[0]}={round(tup[1], 3)}", criteria_set["results"].items()))))


if __name__ == "__main__":
    path = f"{HOME}/biggest_losers.csv"
    analyze_biggest_losers_csv(path)
    print_out_interesting_results()
