from datetime import date

from src.cache import read_json_cache, write_json_cache


#
# Hybrid
#

from datetime import date
from gridsearch_backtest_losers import (
    analyze_biggest_losers_csv,
    build_criteria_set,
    evaluate_results,
    get_lines_from_biggest_losers_csv,
    get_widest_criteria_with_results,
)


def try_hybrid_model(pockets, path, baseline_start_date, is_quality_pocket):
    quality_pockets = list(filter(is_quality_pocket, pockets))

    lines = get_lines_from_biggest_losers_csv(path)

    hybrid_model_trades = []

    criteria_set = build_criteria_set()

    def pocket_includes_line(pocket, line):

        # every criteria must be met
        for dimension_name, segment_name in pocket["names"].items():
            try:
                criteria = criteria_set[dimension_name][segment_name]
            except KeyError:
                # TODO: make 'top_n' like all other criteria by having criteria apply in order
                continue
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


def build_pocket_quality_criteria(
    min_plays=None,
    min_avg_roi=None,
    min_win_percent=None,
    min_g_roi=None,
    min_a_roi=None,
):
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
        return all((criteria(pocket) for criteria in criterion))

    return is_quality_pocket


if __name__ == "__main__":
    write_new_model = True
    model_cache_entry = "modelv2"

    from src.pathing import get_paths

    path = get_paths()["data"]["outputs"]["biggest_losers_csv"]
    baseline_start_date = date(2021, 1, 1)

    if write_new_model:
        pockets = analyze_biggest_losers_csv(path, baseline_start_date)
        write_json_cache(model_cache_entry, pockets)
    else:
        pockets = read_json_cache(model_cache_entry)

    print()
    print("-" * 80)
    baseline_results = get_widest_criteria_with_results(pockets)["results"]
    print(f"baseline with {len(pockets)} pockets", baseline_results)
    print()

    is_quality_pocket = build_pocket_quality_criteria(
        min_win_percent=0.5, min_avg_roi=0.05, min_plays=30
    )

    # TODO: try a hybrid model if pockets are non-overlapping and then use quality + min pocket criteria

    hybrid_results_pockets = try_hybrid_model(
        pockets, path, baseline_start_date, is_quality_pocket
    )
    if not hybrid_results_pockets:
        print("no hybrid model")
        exit(1)
    results, pockets = hybrid_results_pockets

    for pocket in pockets:
        print(
            "  ",
            "  ".join(pocket["names"].values()).ljust(64),
            "| "
            + " ".join(
                list(
                    map(
                        lambda tup: f"{tup[0]}={round(tup[1], 3)}",
                        pocket["results"].items(),
                    )
                )
            ),
        )

    print()
    print("hybrid", results)
