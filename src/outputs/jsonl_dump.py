
import logging
import typing
import json
import datetime


class DateTimeEncoder(json.JSONEncoder):
    # Override the default method
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()


def append_jsonl(path: typing.Optional[str], lines: typing.Iterable[dict]):
    if not lines:
        logging.warning(f"no lines to write to csv {path}")

    f = open(path, "a") if path else None

    for line in lines:
        print(json.dumps(line, sort_keys=True, cls=DateTimeEncoder), file=f)

    if f:
        f.close()


def read_jsonl_lines(path: str) -> typing.Iterator[dict]:
    with open(path) as f:
        yield from (json.loads(line) for line in f)


def main():
    append_jsonl("/tmp/james.jsonl", [
        {"a": 1, "b": 2},
        {"a": 2, "b": 6},
    ])
