from datetime import datetime


def analyze_biggest_losers_csv(path):
    lines = []
    with open(path, "r") as f:
        lines.extend(f.readlines())

    headers = lines[0].strip().split(",")
    print(headers)
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

    print("baseline", evaluate_results(lines))

    passing_criterion = []

    for volume_criteria_name, volume_criteria in {
        '100k shares': lambda v: v > 100000,
        # '200k shares': lambda v: v > 200000,
    }.items():
        for price_criteria_name, price_criteria in {
            "p < 1": lambda p: p < 1,
            "p < 5": lambda p: p < 5,
            # "p < 10": lambda p: p < 10,
            # "p < 20": lambda p: p < 20,
            # "p > 5": lambda p: p > 5,
            # "p > 10": lambda p: p > 10,
            # "p > 20": lambda p: p > 20,
            "all": lambda _: True,
        }.items():
            for weekday_criteria_name, weekday_criteria in {
                # "no f": lambda w: w != 4,  # not friday
                # "no m": lambda w: w != 0,  # not monday
                "no m/f": lambda w: w != 4 and w != 0,  # not monday or friday
                "all": lambda _: True,
            }.items():

                for rank_criteria_name, rank_criteria in {
                    "top 3": lambda r: r >= 3,
                    "top 5": lambda r: r >= 5,
                    # "top 7": lambda r: r >= 7,
                    "top 10": lambda r: r >= 10,
                    "top 20": lambda _: True,
                }.items():
                    filtered_lines = list(filter(
                        lambda l: volume_criteria(l["volume_day_of_loss"]) and price_criteria(
                            l["close_day_of_loss"]) and weekday_criteria(l["day_of_loss"].weekday()) and rank_criteria(l["rank_day_of_loss"]),
                        lines))

                    results = evaluate_results(filtered_lines)
                    if not results:
                        continue

                    if results["roi"] < 5:
                        continue

                    if results["average_roi"] < .02:
                        continue

                    # if results["win_rate"] < .55:
                    #     continue

                    # if results["plays"] < 300:
                    #     continue

                    passing_criterion.append({
                        "volume": volume_criteria_name,
                        "price": price_criteria_name,
                        "weekday": weekday_criteria_name,
                        "rank": rank_criteria_name,
                        "results": results,
                    })

    for criteria in sorted(passing_criterion, key=lambda c: c["results"]["win_rate"], reverse=True):
        print(f"{criteria['volume']}\t{criteria['price']}\t{criteria['weekday']}\t{criteria['rank']}\t\t",
              "average_roi={average_roi:1.2f}% win_rate={win_rate:2.1f} plays={plays} roi={roi:.1f} ".format(
                  average_roi=criteria['results']["average_roi"] * 100,
                  win_rate=criteria['results']["win_rate"] * 100,
                  plays=criteria['results']["plays"],
                  roi=criteria['results']["roi"],))


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
