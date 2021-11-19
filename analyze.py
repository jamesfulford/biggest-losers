from datetime import date, datetime, timedelta
import os

HOME = os.environ['HOME']


def analyze_biggest_losers_csv(path):
    lines = []
    with open(path, "r") as f:
        lines.extend(f.readlines())

    headers = lines[0].strip().split(",")
    # remove newlines and header row
    lines = [l.strip() for l in lines[1:]]

    # convert to dicts
    lines = [dict(zip(headers, l.strip().split(","))) for l in lines]

    # print(lines[0])

    lines = [{
        "day_of_loss": datetime.strptime(l["day_of_loss"], "%Y-%m-%d").date(),
        "day_of_loss_weekday": int(l["day_of_loss_weekday"]),
        "day_of_loss_month": int(l["day_of_loss_month"]),

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

        "spy_day_of_loss_percent_change": float(l["spy_day_of_loss_percent_change"]),
        "spy_day_of_loss_intraday_percent_change": float(l["spy_day_of_loss_intraday_percent_change"]),

        "open_day_after": float(l["open_day_after"]),
        "close_day_after": float(l["close_day_after"]),
        "high_day_after": float(l["high_day_after"]),
        "low_day_after": float(l["low_day_after"]),
        "volume_day_after": float(l["volume_day_after"]),

        "overnight_strategy_roi": float(l["overnight_strategy_roi"]),
        "overnight_strategy_is_win": int(l["overnight_strategy_is_win"]),
    } for l in lines]

    unmapped_fields_in_csv = set(headers) - set(lines[0].keys())
    if unmapped_fields_in_csv:
        print("WARNING update code to include these fields:",
              unmapped_fields_in_csv)

    #
    # ignore rows before this date
    #
    baseline_start_date = date.today() - timedelta(weeks=52)

    def baseline_criteria(t):
        return t["volume_day_of_loss"] > 100000 and t["day_of_loss"] > baseline_start_date

    #
    # calculate results of always following baseline
    #
    lines = list(filter(baseline_criteria, lines))

    for l in lines:
        l["close_to_open_roi"] = (
            l["open_day_after"] - l["close_day_of_loss"]) / l["close_day_of_loss"]

    # reference what you can build subsets off of
    # print(lines[0])

    baseline_results = evaluate_results(lines)
    print("baseline", baseline_results)
    print()

    #
    # explore what stricter results might do for you
    #

    criteria_results = []

    #
    # market up/down
    #
    spy_direction_criterion = {
        # "1% up  ": lambda t: t["spy_day_of_loss_percent_change"] > 0.01,
        # ".5 up  ": lambda t: t["spy_day_of_loss_percent_change"] > 0.005,
        # "up     ": lambda t: t["spy_day_of_loss_percent_change"] > 0,
        # "down   ": lambda t: t["spy_day_of_loss_percent_change"] < 0,
        "-.5%spy": lambda t: t["spy_day_of_loss_percent_change"] < 0.005,
        "-1%spy ": lambda t: t["spy_day_of_loss_percent_change"] < 0.01,
        "*spy   ": lambda _: True,
    }

    #
    # volume
    #
    volume_criterion = {
        # '100k shares': lambda t: t["volume_day_of_loss"] > 100000,
        # '200k shares': lambda t: t["volume_day_of_loss"] > 200000,
        '*vol': lambda _: True,
    }

    #
    # closing price
    #
    price_criterion = {
        "p < 1 ": lambda t: t["close_day_of_loss"] < 1,
        # "p < 5 ": lambda t: t["close_day_of_loss"] < 5,
        # "p < 10": lambda t: t["close_day_of_loss"] < 10,
        # "p < 20": lambda t: t["close_day_of_loss"] < 20,
        # "p > 5 ": lambda t: t["close_day_of_loss"] > 5,
        # "p > 10": lambda t: t["close_day_of_loss"] > 10,
        # "p > 20": lambda t: t["close_day_of_loss"] > 20,
        # "all $ ": lambda _: True,
    }

    #
    # day of week
    #
    weekday_criterion = {
        "no f  ": lambda t: t["day_of_loss"].weekday() != 4,  # not friday
        "no m  ": lambda t: t["day_of_loss"].weekday() != 0,  # not monday
        # not monday or friday
        "no m/f": lambda t: t["day_of_loss"].weekday() != 4 and t["day_of_loss"].weekday() != 0,
        "all d ": lambda _: True,
    }

    #
    # overall biggest loser rank
    #
    def build_rank_criterion(rank):
        def rank_criterion(t):
            return t["rank_day_of_loss"] <= rank
        return rank_criterion
    rank_criterion = {}
    for i in [11, 20]:
        rank_criterion[f"top {i}"] = build_rank_criterion(i)

    #
    # intraday % change
    #
    intraday_loss_criterion = {
        "down intr": lambda t: t["intraday_percent_change_day_of_loss"] < 0,
        "-5% intr ": lambda t: t["intraday_percent_change_day_of_loss"] < -.05,
        "any intr ": lambda _: True,
        # "intraday gain": lambda t: t["intraday_percent_change_day_of_loss"] > 0,
        # "up 5% intr": lambda t: t["intraday_percent_change_day_of_loss"] > .05,
    }

    def build_intraday_loss_criterion(percent):
        def intraday_loss_criterion(t):
            return t["intraday_percent_change_day_of_loss"] < percent
        return intraday_loss_criterion
    for i in []:
        percent = i / 100
        intraday_loss_criterion[f"intr < {percent}"] = build_intraday_loss_criterion(
            percent)

    # TODO: test based off of total loss
    # TODO: change spreadsheet source to get even more losers, maybe just penny stock with enough volume

    def try_criterion(criterion):
        filtered_lines = lines
        for _criteria_name, criteria in criterion.items():
            new_lines = list(filter(criteria, filtered_lines))
            filtered_lines = new_lines

        results = evaluate_results(filtered_lines)
        if not results:
            return

        criteria_results.append({
            "names": criterion.keys(),
            "results": results,
        })

    for spy_direction_criteria_name, spy_direction_criteria in spy_direction_criterion.items():
        for volume_criteria_name, volume_criteria in volume_criterion.items():
            for price_criteria_name, price_criteria in price_criterion.items():
                for weekday_criteria_name, weekday_criteria in weekday_criterion.items():
                    for rank_criteria_name, rank_criteria in rank_criterion.items():
                        for intraday_loss_criteria_name, intraday_loss_criteria in intraday_loss_criterion.items():
                            try_criterion({
                                spy_direction_criteria_name: spy_direction_criteria,
                                volume_criteria_name: volume_criteria,
                                price_criteria_name: price_criteria,
                                weekday_criteria_name: weekday_criteria,
                                rank_criteria_name: rank_criteria,
                                intraday_loss_criteria_name: intraday_loss_criteria,
                            })

    criteria_to_evaluate = baseline_results.keys()
    criteria_to_evaluate = ["roi", "g_roi"]
    for key_criteria in criteria_to_evaluate:
        if key_criteria == "plays" or key_criteria == "days":
            # of course no subsets have a bigger cardinality, don't bother printing
            continue

        passing_criterion_sets = list(filter(
            lambda r: r["results"][key_criteria] > baseline_results[key_criteria], criteria_results))

        # filter out shallow/small results
        minimum_percent_plays = 0
        passing_criterion_sets = list(filter(
            lambda r: r["results"]["plays"] > minimum_percent_plays * baseline_results["plays"], passing_criterion_sets))

        minimum_trading_days_percent = 0
        passing_criterion_sets = list(filter(
            lambda r: r["results"]["days"] > minimum_trading_days_percent * baseline_results["days"], passing_criterion_sets))

        show_top = 10
        print(f"subsets which outperform baseline on {key_criteria}:", len(
            passing_criterion_sets))
        for criteria_set in sorted(passing_criterion_sets, key=lambda c: c["results"]["roi"], reverse=True)[:show_top]:

            print("  ", "\t".join(
                criteria_set["names"]), "|" + " ".join(list(map(lambda tup: f"{tup[0]}={round(tup[1], 3)}", criteria_set["results"].items()))))


def evaluate_results(lines):
    if not lines:
        return None

    plays = len(lines)

    if plays < 10:
        return None

    total_roi = sum(list(map(lambda l: l["close_to_open_roi"], lines)))
    average_roi = total_roi / plays

    win_rate = sum(
        list(map(lambda l: 1 if l["close_to_open_roi"] > 0 else 0, lines))) / plays

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
            today_roi += get_weight(trade, trades) * trade["close_to_open_roi"]

        # just take returns, do not reinvest, only withdraw to replenish original capital
        arithmetic_roi += today_roi

        # reinvest returns, every day invest 1/3 of balance (cash account)
        geometric_current_balance = (
            1/3) * geometric_current_balance * (1 + today_roi) + (2/3) * geometric_current_balance

    # TODO: calculate drawdown and other stats

    return {
        "roi": arithmetic_roi,
        "a_roi": arithmetic_roi,
        "g_roi": geometric_current_balance,
        "plays": plays,
        "avg_roi": average_roi,
        "win%": win_rate,
        "days": trading_days,
    }


if __name__ == "__main__":
    path = f"{HOME}/biggest_losers.csv"
    analyze_biggest_losers_csv(path)
