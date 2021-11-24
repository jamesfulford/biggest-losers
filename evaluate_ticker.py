from datetime import date

from cache import read_json_cache
from analyze import build_criteria_set
from functools import reduce

model = read_json_cache("modelv0")
criteria_set = build_criteria_set()


def find_matching_results(values, minimum_plays=100):
    descriptor = {}
    for criteria_group_name, criteria_group in criteria_set.items():
        descriptor[criteria_group_name] = []
        for criteria_name, criteria in criteria_group.items():
            if criteria(values):
                descriptor[criteria_group_name].append(
                    criteria_name)

    def result_matches_criteria(result, descriptor):
        if result["results"]["plays"] < minimum_plays:
            return False

        for criteria_group_name, criteria_set in result["names"].items():
            if criteria_set not in descriptor[criteria_group_name]:
                return False
        return True

    matching_results = list(filter(
        lambda r: result_matches_criteria(r, descriptor), model))

    print(len(matching_results))

    tightest_match = reduce(
        lambda a, x: a if a["results"]["plays"] < x["results"]["plays"] else x, matching_results)

    return tightest_match


best_match = find_matching_results({
    "spy_day_of_loss_percent_change": -0.011,
    "volume_day_of_loss": 123456,
    "close_day_of_loss": 0.93,
    "day_of_loss": date(2021, 11, 22),
    "rank_day_of_loss": 4,
    "intraday_percent_change_day_of_loss": -0.21,
    "ticker": "ASDF"
}, minimum_plays=1)
print(list(best_match["names"].values()))
print(best_match["results"])

# nodemon -e py -x "python3 evaluate_ticker.py"
