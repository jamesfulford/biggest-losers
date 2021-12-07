import os
import json


HOME = os.environ['HOME']


def read_json_cache(key):
    path = f"{HOME}/data/{key}"
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def write_json_cache(key, value):
    path = f"{HOME}/data/{key}"
    with open(path, 'w') as f:
        json.dump(value, f)


def delete_json_cache(key):
    path = f"{HOME}/data/{key}"
    try:
        os.remove(path)
    except Exception:
        pass
