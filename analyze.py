from datetime import date, datetime, timedelta
import os
from itertools import product

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

    lines = [{
        "day_of_loss": datetime.strptime(l["day_of_loss"], "%Y-%m-%d").date(),
        "day_after": datetime.strptime(l["day_after"], "%Y-%m-%d").date(),
        "ticker": l["ticker"],

        "open_day_of_loss": float(l["open_day_of_loss"]),
        "close_day_of_loss": float(l["close_day_of_loss"]),
        "high_day_of_loss": float(l["high_day_of_loss"]),
        "low_day_of_loss": float(l["low_day_of_loss"]),
        "volume_day_of_loss": float(l["volume_day_of_loss"]),

        "close_to_close_percent_change_day_of_loss": float(l["close_to_close_percent_change_day_of_loss"]),
        "rank_day_of_loss": int(l["rank_day_of_loss"]),

        "open_day_after": float(l["open_day_after"]),
        "close_day_after": float(l["close_day_after"]),
        "high_day_after": float(l["high_day_after"]),
        "low_day_after": float(l["low_day_after"]),
        "volume_day_after": float(l["volume_day_after"]),
    } for l in lines]

    for l in lines:
        l["close_to_open_roi"] = (
            l["open_day_after"] - l["close_day_of_loss"]) / l["close_day_of_loss"]

    baseline_results = evaluate_results(lines)
    print("baseline", baseline_results)

    passing_criterion_sets = []

    volume_criterion = {
        '100k shares': lambda t: t["volume_day_of_loss"] > 100000,
        # '200k shares': lambda t: t["volume_day_of_loss"] > 200000,
    }

    price_criterion = {
        "p < 1": lambda t: t["close_day_of_loss"] < 1,
        "p < 5": lambda t: t["close_day_of_loss"] < 5,
        # "p < 10": lambda p: t["close_day_of_loss"] < 10,
        # "p < 20": lambda p: t["close_day_of_loss"] < 20,
        # "p > 5": lambda p: t["close_day_of_loss"] > 5,
        # "p > 10": lambda p: t["close_day_of_loss"] > 10,
        # "p > 20": lambda p: t["close_day_of_loss"] > 20,
        "all": lambda _: True,
    }

    weekday_criterion = {
        # "no f": lambda t: t["day_of_loss"].weekday() != 4,  # not friday
        # "no m": lambda t: t["day_of_loss"].weekday() != 0,  # not monday
        # not monday or friday
        "no m/f": lambda t: t["day_of_loss"].weekday() != 4 and t["day_of_loss"].weekday() != 0,
        "all": lambda _: True,
    }

    time_horizon_criterion = {
        # "since Nov 18 2019": lambda _: True,
        # "since July 2020": lambda t: t["day_of_loss"] > date(2020, 7, 1),
        # "since Jan 2021": lambda t: t["day_of_loss"] > date(2021, 7, 1),
        "last 13 weeks": lambda t: t["day_of_loss"] > date.today() - timedelta(weeks=13),
    }

    rank_criterion = {
        "top 3": lambda t: t["rank_day_of_loss"] >= 3,
        "top 5": lambda t: t["rank_day_of_loss"] >= 5,
        # "top 7": lambda t: t["rank_day_of_loss"] >= 7,
        "top 10": lambda t: t["rank_day_of_loss"] >= 10,
        "top 20": lambda _: True,
    }

    def try_criterion(criterion):
        filtered_lines = lines
        for criteria in criterion:
            filtered_lines = list(
                filter(criteria, filtered_lines))

        results = evaluate_results(filtered_lines)
        if not results:
            return

        if results["roi"] < 20:
            return

        # if results["average_roi"] < .02:
        #     return

        # if results["win_rate"] < .55:
        #     return

        # if results["plays"] < 300:
        #     return

        passing_criterion_sets.append({
            "volume": volume_criteria_name,
            "price": price_criteria_name,
            "weekday": weekday_criteria_name,
            "rank": rank_criteria_name,
            "time_horizon": time_horizon_name,
            "results": results,
        })

    for volume_criteria_name, volume_criteria in volume_criterion.items():
        for price_criteria_name, price_criteria in price_criterion.items():
            for weekday_criteria_name, weekday_criteria in weekday_criterion.items():
                for rank_criteria_name, rank_criteria in rank_criterion.items():
                    for time_horizon_name, time_horizon_criteria in time_horizon_criterion.items():
                        try_criterion([
                            volume_criteria,
                            price_criteria,
                            weekday_criteria,
                            rank_criteria,
                            time_horizon_criteria,
                        ])

    for criteria_set in sorted(passing_criterion_sets, key=lambda c: c["results"]["win_rate"], reverse=True):
        print(f"{criteria_set['volume']}\t{criteria_set['price']}\t{criteria_set['weekday']}\t{criteria_set['rank']}\t{criteria_set['time_horizon']}\t",
              "average_roi={average_roi:1.2f}% win_rate={win_rate:2.1f} plays={plays} roi={roi:.1f} ".format(
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

    return {"roi": total_roi, "plays": plays, "average_roi": average_roi, "win_rate": win_rate}


if __name__ == "__main__":
    path = f"{HOME}/biggest_losers.csv"
    analyze_biggest_losers_csv(path)
