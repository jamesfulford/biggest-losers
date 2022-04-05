import argparse
from datetime import date, datetime, time, timedelta
import logging
import os
from typing import Iterator, Optional, Tuple
from src.backtest.chronicle.read import ChronicleEntry, read_backtest_chronicle, read_recorded_chronicle

from src.outputs.pathing import get_paths


def get_chronicled_scanners() -> list[str]:
    basepath = get_paths()['data']['dir']
    path = os.path.join(basepath, 'chronicles')
    return [p for p in sorted(os.listdir(path)) if "." not in p]


def _get_chronicles(scanner_name: str, chron_type: str):
    basepath = get_paths()['data']['dir']
    path = os.path.join(
        basepath, 'chronicles', scanner_name, chron_type)

    paths = os.listdir(path)
    return [
        (date(*(int(s) for s in path.split("-")
         [:3])), path.split("-")[3].replace(".jsonl", ""))
        for path in paths if path.endswith(".jsonl")
    ]


def get_recorded_chronicles(scanner_name: str):
    return _get_chronicles(scanner_name, 'live')


def get_backtest_chronicles(scanner_name: str):
    return _get_chronicles(scanner_name, 'backtest')


def get_chronicle_span(feed: Iterator[ChronicleEntry]) -> Tuple[Optional[datetime], Optional[datetime], Optional[list[Tuple[datetime, datetime]]]]:
    first_row = next(feed, None)
    if not first_row:
        return None, None, None

    last_row = first_row
    gaps = []
    for row in feed:
        if row["now"] - last_row["now"] > timedelta(minutes=1):
            gaps.append((last_row["now"], row["now"]))
        last_row = row

    return first_row['now'], last_row['now'], gaps


def is_partial_recording(recording) -> bool:
    return recording['end'] - recording['start'] < timedelta(hours=6, minutes=29)


def is_skippy_recording(recording) -> bool:
    return not not recording['gaps']


def list_chronicle_details(scanner_name: str, chron_type: str):
    chronicles = []
    if chron_type == "recorded":
        chronicles = get_recorded_chronicles(scanner_name)
    elif chron_type == "backtest":
        chronicles = get_backtest_chronicles(scanner_name)
    else:
        raise ValueError(f"Invalid chronicle type: {chron_type}")

    for chronicle in sorted(chronicles):
        if chron_type == "recorded":
            feed = read_recorded_chronicle(
                scanner_name, chronicle[0], chronicle[1])
        elif chron_type == "backtest":
            feed = read_backtest_chronicle(
                scanner_name, chronicle[0], chronicle[1])
        else:
            # Should never happen because of earlier assertions
            continue

        start, end, gaps = get_chronicle_span(feed)
        if not start or not end or gaps is None:
            logging.warn(
                f"{scanner_name} {chron_type} {chronicle[0]} {chronicle[1]} is empty, skipping")
            continue

        yield {
            "scanner_name": scanner_name,
            "chronicle_type": chron_type,
            "chronicle_date": chronicle[0],
            "chronicle_name": chronicle[1],
            "gaps": gaps,
            "start": start,
            "end": end,
        }


def is_chronicle_good_start_time(chronicle) -> bool:
    return chronicle['start'].time() == time(9, 31)


def is_chronicle_good_end_time(chronicle) -> bool:
    return chronicle['end'].time() == time(16, 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('scanner_name', type=str,
                        choices=get_chronicled_scanners())
    parser.add_argument('chronicle_type', type=str,
                        choices=['recorded', 'backtest'])
    args = parser.parse_args()

    scanner_name = args.scanner_name
    chron_type = args.chronicle_type

    details = list(list_chronicle_details(scanner_name, chron_type))

    for detail in details:
        print(
            f"{detail['chronicle_date']} {detail['chronicle_name']}")
        print(f"  start: {detail['start']}")
        print(f"    end: {detail['end']}")
    print()

    if chron_type == "recorded":
        # recorded chronicles only ever last 1 day.

        for detail in details:
            # Issues that can happen:
            # 1. Recording is too short ("partial recording")
            #    (may be able to combine 2 recordings, but may have different metadata e.g. commit_id)
            # 2. Recording has gaps ("skippy recording")
            #    (because scanning was too slow)
            #    (NOTE: this may not be an issue for low-throughput scanners)
            is_healthy = not (is_partial_recording(detail)
                              or is_skippy_recording(detail))
            print(detail['start'].date(), "good" if is_healthy else "bad")
            if is_partial_recording(detail):
                print("\tpartial recording")
            if is_skippy_recording(detail):
                print("\tskippy recording")

        print()
        print("Partial recordings:")
        partial_recordings_by_day = {}
        for detail in (d for d in details if is_partial_recording(d)):
            key = detail['start'].date()
            partial_recordings_by_day[key] = partial_recordings_by_day.get(
                key, []) + [detail]

        for day, partial_recordings in partial_recordings_by_day.items():
            spans = [(d['start'], d['end']) for d in sorted(
                partial_recordings, key=lambda d: d['start'])]
            print(day)
            for span in spans:
                print(
                    f"\t{span[0].time()} - {span[1].time()} (spans {int((span[1] - span[0]).total_seconds() // 60)}m)")

        print()
        print("Minutes of gaps:")
        for detail in (d for d in details if is_skippy_recording(d)):
            print(detail['start'].date(), sum((d[1] - d[0]).total_seconds()
                                              for d in detail['gaps']) // 60)

            for gap_start, gap_end in detail['gaps'][:10]:
                print(
                    f'\t{gap_start.time()} - {gap_end.time()} ({int((gap_end - gap_start).total_seconds() // 60) - 1}m missing)')
            if len(detail['gaps']) > 10:
                print('\t...')

    elif chron_type == "backtest":
        for detail in details:
            # backtest chronicles can be longer than 1 day.
            # Issues that can happen:
            # 1. Recording does not start or end at correct times
            #    (because backtest was built midday)
            is_healthy = is_chronicle_good_start_time(
                detail) and is_chronicle_good_end_time(detail)
            print(
                f"{detail['chronicle_date']} {detail['chronicle_name']:>7} {'good' if is_healthy else 'bad'}")

            if not is_chronicle_good_start_time(detail):
                print("  atypical start time:", detail['start'])
            if not is_chronicle_good_end_time(detail):
                print("  atypical end time:", detail['end'])

    else:
        raise ValueError(f"Invalid chronicle type: {chron_type}")
