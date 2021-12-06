from datetime import date, datetime


def is_warrant(ticker):
    return (ticker.upper().endswith("W") or ".WS" in ticker.upper())


#
# Skipping days
#

def get_skipped_days():
    lines = []
    with open("days_to_skip.csv", "r") as f:
        lines.extend(f.readlines())

    headers = lines[0].strip().split(",")
    # remove newlines and header row
    lines = [l.strip() for l in lines[1:]]

    # convert to dicts
    raw_dict_lines = [dict(zip(headers, l.strip().split(","))) for l in lines]

    lines = [{
        "date": datetime.strptime(d["date"], "%Y-%m-%d").date(),
        "reason": d["reason"]
    } for d in raw_dict_lines]

    return lines


_skipped_days_set = set(
    map(lambda d: d["date"].strftime("%Y-%m-%d"), get_skipped_days()))


def is_skipped_day(today):
    return today.strftime("%Y-%m-%d") in _skipped_days_set
