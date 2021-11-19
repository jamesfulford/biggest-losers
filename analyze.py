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
        return t["volume_day_of_loss"] > 100000 and t["day_of_loss"] > baseline_start_date and t["close_day_of_loss"] < 1

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

    spy_direction_criterion = {
        "1% up  ": lambda t: t["spy_day_of_loss_percent_change"] > 0.01,
        ".5 up  ": lambda t: t["spy_day_of_loss_percent_change"] > 0.005,
        "up     ": lambda t: t["spy_day_of_loss_percent_change"] > 0,
        "down   ": lambda t: t["spy_day_of_loss_percent_change"] < 0,
        ".5 down": lambda t: t["spy_day_of_loss_percent_change"] < 0.005,
        "1% down": lambda t: t["spy_day_of_loss_percent_change"] < 0.01,
    }

    volume_criterion = {
        '100k shares': lambda t: t["volume_day_of_loss"] > 100000,
        '200k shares': lambda t: t["volume_day_of_loss"] > 200000,
    }

    price_criterion = {
        "p < 1 ": lambda t: t["close_day_of_loss"] < 1,
        "p < 5 ": lambda t: t["close_day_of_loss"] < 5,
        "p < 10": lambda t: t["close_day_of_loss"] < 10,
        "p < 20": lambda t: t["close_day_of_loss"] < 20,
        "p > 5 ": lambda t: t["close_day_of_loss"] > 5,
        "p > 10": lambda t: t["close_day_of_loss"] > 10,
        "p > 20": lambda t: t["close_day_of_loss"] > 20,
        "all $ ": lambda _: True,
    }

    weekday_criterion = {
        "no f  ": lambda t: t["day_of_loss"].weekday() != 4,  # not friday
        "no m  ": lambda t: t["day_of_loss"].weekday() != 0,  # not monday
        # not monday or friday
        "no m/f": lambda t: t["day_of_loss"].weekday() != 4 and t["day_of_loss"].weekday() != 0,
        "all d ": lambda _: True,
    }

    rank_criterion = {
        "top 3 ": lambda t: t["rank_day_of_loss"] >= 3,
        "top 5 ": lambda t: t["rank_day_of_loss"] >= 5,
        # "top 7 ": lambda t: t["rank_day_of_loss"] >= 7,
        "top 10": lambda t: t["rank_day_of_loss"] >= 10,
        "top 20": lambda _: True,
    }

    def try_criterion(criterion):

        filtered_lines = lines
        for criteria in criterion.values():
            filtered_lines = list(
                filter(criteria, filtered_lines))

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
                        try_criterion({
                            spy_direction_criteria_name: spy_direction_criteria,
                            volume_criteria_name: volume_criteria,
                            price_criteria_name: price_criteria,
                            weekday_criteria_name: weekday_criteria,
                            rank_criteria_name: rank_criteria,
                        })

    for key_criteria in baseline_results.keys():
        if key_criteria == "plays":
            # of course no subsets have a bigger cardinality, don't bother printing
            continue

        passing_criterion_sets = list(filter(
            lambda r: r["results"][key_criteria] > baseline_results[key_criteria], criteria_results))

        # filter out shallow/small results
        minimum_percent_plays = .05
        passing_criterion_sets = list(filter(
            lambda r: r["results"]["plays"] > minimum_percent_plays * baseline_results["plays"], passing_criterion_sets))

        show_top = 3
        print(f"subsets which outperform baseline on {key_criteria}:", len(
            passing_criterion_sets))
        for criteria_set in sorted(passing_criterion_sets, key=lambda c: c["results"][key_criteria], reverse=True)[:show_top]:

            print("\t", "\t".join(criteria_set["names"]), "\t\t"
                  "avg={average_roi:1.2f}% win={win_rate:2.1f} plays={plays} roi={roi:.1f} ".format(
                average_roi=criteria_set['results']["average_roi"] * 100,
                win_rate=criteria_set['results']["win_rate"] * 100,
                plays=criteria_set['results']["plays"],
                roi=criteria_set['results']["roi"],))


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

    # TODO: calculate drawdown and other stats

    return {"roi": total_roi, "plays": plays, "average_roi": average_roi, "win_rate": win_rate}


if __name__ == "__main__":
    path = f"{HOME}/biggest_losers.csv"
    analyze_biggest_losers_csv(path)
