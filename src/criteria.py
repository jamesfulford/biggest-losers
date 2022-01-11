from datetime import datetime
import os


def is_warrant(ticker):
    return ticker.upper().endswith("W") or ".WS" in ticker.upper()


def is_unit(ticker):
    return ticker.upper().endswith("U") or ".U" in ticker.upper()


def is_stock(ticker):
    return not is_warrant(ticker) and not is_unit(ticker) and ticker.upper() == ticker


#
# Skipping days
#


dir_of_script = os.path.dirname(os.path.abspath(__file__))
days_to_skip_csv_path = os.path.abspath(
    os.path.join(dir_of_script, "..", "days_to_skip.csv")
)


def get_skipped_days():
    lines = []
    with open(days_to_skip_csv_path, "r") as f:
        lines.extend(f.readlines())

    headers = lines[0].strip().split(",")
    # remove newlines and header row
    lines = [l.strip() for l in lines[1:]]

    # convert to dicts
    raw_dict_lines = [dict(zip(headers, l.strip().split(","))) for l in lines]

    lines = [
        {"date": datetime.strptime(d["date"], "%Y-%m-%d").date(), "reason": d["reason"]}
        for d in raw_dict_lines
    ]

    return lines


_skipped_days_set = set(
    map(lambda d: d["date"].strftime("%Y-%m-%d"), get_skipped_days())
)


def is_skipped_day(today):
    return today.strftime("%Y-%m-%d") in _skipped_days_set
