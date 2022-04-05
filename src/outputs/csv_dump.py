from datetime import datetime, date
from itertools import chain
import logging
from typing import Any, Iterable, Iterator, Optional


def serialize(v: Any) -> str:
    t = type(v)
    if t == str:
        return v
    elif t == type(None):
        return ""
    elif t == bool:
        return str(int(v))
    elif t == float:
        return str(round(v, 4))
    elif t == int:
        return str(v)
    elif t == datetime or t == date:
        return v.isoformat()
    else:
        logging.warning(f"WARNING: unknown type {t} for {v}")
        return str(v)


def write_csv(path: Optional[str], lines: Iterator[dict], headers: Optional[list[str]] = None) -> int:
    first_line = next(lines, None)
    if not first_line:
        logging.warning(
            f"write_csv: no data to write to {path}, not writing anything.")
        return 0

    if not headers:
        headers = []

    f = open(path, "w") if path else None

    # write provided headers first, in order, then rest of keys in alphabetical order
    existing_headers = set(first_line.keys())
    headers = headers + sorted(existing_headers.difference(set(headers)))
    print(",".join(headers), file=f)

    line_count = 0
    for line in chain([first_line], lines):
        print(",".join(map(lambda h: serialize(line.get(h, None)), headers)), file=f)
        line_count += 1
        if line_count % 200 == 0:
            logging.info(
                f"write_csv: wrote {line_count} lines so far, continuing...")

    if f:
        f.close()

    return line_count


if __name__ == "__main__":

    def jam():
        yield {"a": 1, "b": 2, "d": 3, "c": 4}
        yield {"a": 1, "b": 2, "d": 3, "c": 5}

    write_csv("/tmp/james.csv", jam(), ["d", "b"])

    expected_str = "d,b,a,c\n"
    expected_str += "3,2,1,4\n"
    expected_str += "3,2,1,5\n"

    output_csv_content = open("/tmp/james.csv").read()

    assert expected_str == output_csv_content
