
import json
import datetime

from src.trading_day import MARKET_TIMEZONE


class DateTimeEncoder(json.JSONEncoder):
    # Override the default method
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()


def to_json_string(o) -> str:
    return json.dumps(o, sort_keys=True, cls=DateTimeEncoder)


class MarketTimezoneDateTimeDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(
            self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        for key, value in obj.items():
            if isinstance(value, str) and "T" in value:
                obj[key] = datetime.datetime.fromisoformat(
                    value).astimezone(MARKET_TIMEZONE)
        return obj


def from_json_string(s: str):
    return json.loads(s, cls=MarketTimezoneDateTimeDecoder)


def write_json(path: str, o):
    with open(path, 'w') as f:
        print(to_json_string(o), file=f)


def read_json(path: str):
    with open(path, 'r') as f:
        return from_json_string(f.read())
