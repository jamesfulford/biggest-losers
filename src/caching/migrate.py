from functools import cache
import logging
import os
import shutil
from src.caching.basics import get_matching_entries
from src.outputs.pathing import get_paths


def main():
    cache_dir = get_paths()["data"]["cache"]["dir"]

    for entry in get_matching_entries(""):
        path = os.path.join(cache_dir, entry)

        if os.path.isdir(path):
            continue

        target_path = path
        if entry.startswith("grouped_aggs_"):
            target_path = os.path.join(
                cache_dir, "polygon/grouped_aggs/", entry.replace("grouped_aggs_", ""))
        elif entry.startswith("candles_"):
            target_path = os.path.join(
                cache_dir, "finnhub/candles/", entry.replace("candles_", ""))
        elif entry.startswith("polygon_candles_"):
            target_path = os.path.join(
                cache_dir, "polygon/candles/", entry.replace("polygon_candles_", ""))
        elif entry.startswith("tickers_"):
            target_path = os.path.join(
                cache_dir, "polygon/ticker_details/", entry.replace("tickers_", ""))
        elif entry.startswith("fundamentals_"):
            target_path = os.path.join(
                cache_dir, "td/fundamentals/", entry.replace("fundamentals_", ""))
        elif entry.startswith("yh_v3_stats_"):
            target_path = os.path.join(
                cache_dir, "yh_finance/v3_stats/", entry.replace("yh_v3_stats_", ""))
        else:
            logging.warn(f"Unknown cache entry: {entry}")
            continue

        print(f"{path} -> {target_path}")
        shutil.move(path, target_path)
