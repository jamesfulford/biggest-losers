from datetime import datetime
from functools import lru_cache
import os
import json

from src.pathing import get_paths


def _get_cache_path(key: str) -> str:
    return os.path.join(get_paths()["data"]["cache"]['dir'], key)


@lru_cache(maxsize=100)
def read_json_cache(key: str):
    path = _get_cache_path(key)
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def write_json_cache(key: str, value) -> None:
    path = _get_cache_path(key)
    with open(path, 'w') as f:
        json.dump(value, f)


def delete_json_cache(key: str) -> None:
    path = _get_cache_path(key)
    try:
        os.remove(path)
    except Exception:
        pass


def clear_json_cache(substring: str) -> None:
    for key in os.listdir(get_paths()["data"]["cache"]['dir']):
        if substring in key:
            delete_json_cache(key)


def get_entry_time(key: str) -> datetime:
    path = _get_cache_path(key)
    return datetime.fromtimestamp(os.path.getctime(path))


def get_matching_entries(substring: str) -> list:
    return [key for key in os.listdir(get_paths()["data"]["cache"]['dir']) if substring in key]
