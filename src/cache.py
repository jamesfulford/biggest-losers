import os
import json

from src.pathing import get_paths


def _get_cache_path(key):
    return os.path.join(get_paths()["data"]["cache"]['dir'], key)


def read_json_cache(key):
    path = _get_cache_path(key)
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def write_json_cache(key, value):
    path = _get_cache_path(key)
    with open(path, 'w') as f:
        json.dump(value, f)


def delete_json_cache(key):
    path = _get_cache_path(key)
    try:
        os.remove(path)
    except Exception:
        pass
