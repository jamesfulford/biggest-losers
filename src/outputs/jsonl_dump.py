
import logging
import pprint
import typing
from src.outputs import json_dump


def append_jsonl(path: typing.Optional[str], lines: typing.Iterable[dict]):
    if not lines:
        logging.warning(f"no lines to write to csv {path}")

    if path:
        f = open(path, "a")
        for line in lines:
            print(json_dump.to_json_string(line), file=f)
        f.close()
    else:
        pprint.pprint(lines)


def read_jsonl_lines(path: str) -> typing.Iterator[dict]:
    with open(path) as f:
        yield from (json_dump.from_json_string(line) for line in f)


def main():
    append_jsonl("/tmp/james.jsonl", [
        {"a": 1, "b": 2},
        {"a": 2, "b": 6},
    ])
