from datetime import datetime, time, timedelta
import logging
from typing import Iterator, Optional, Tuple
import typing
from src.backtest.chronicle import crud
from src.backtest.chronicle.types import Snapshot


def get_chronicle_span(feed: Iterator[Snapshot]) -> Tuple[Optional[datetime], Optional[datetime], Optional[list[Tuple[datetime, datetime]]]]:
    first_row = next(feed, None)
    if not first_row:
        return None, None, None

    last_row = first_row
    gaps = []
    for row in feed:
        if row.now - last_row.now > timedelta(minutes=1):
            gaps.append((last_row.now, row.now))
        last_row = row

    return first_row.now, last_row.now, gaps


def main():
    chronicle_names = crud.list()
    for chronicle_name in chronicle_names:
        print(chronicle_name)
        chronicle = crud.get(chronicle_name)
        print(f'    meta.start: {chronicle.metadata.start}')
        print(f'    meta.end  : {chronicle.metadata.end  }')
        print(f'    meta.class: {chronicle.metadata.classification  }')
        print(f'    meta.origin: {chronicle.metadata.origin  }')
        print(f'    meta.commit: {chronicle.metadata.commit  }')

        start, end, gaps = get_chronicle_span(iter(chronicle.snapshots))
        if not start or not end or gaps is None:
            logging.warn(
                f"{chronicle_name} is empty, skipping")
        start = typing.cast(datetime, start)
        end = typing.cast(datetime, end)

        # TODO: are chronicle snapshot timestamps supposed to be end of minute (9:31-16:00) or start of minute (9:30-15:59)?
        # TODO: figure out why create.py is doing deep premarket
        if start.time() != time(9, 31):
            logging.warn(
                f"{chronicle_name} has bad start time of {start.time()}")

        if end.time() != time(16, 0):
            logging.warn(
                f"{chronicle_name} has bad end time of {end.time()}")

        if chronicle.metadata.is_recorded():
            # Issues that can happen:
            # 1. Recording is too short ("partial recording")
            #    (may be able to combine 2 recordings, but may have different metadata e.g. commit_id)
            # 2. Recording has gaps ("skippy recording")
            #    (because scanning was too slow)
            #    (NOTE: this may not be an issue for low-throughput scanners)
            if end - start < timedelta(hours=6, minutes=29):
                logging.warn(
                    f"{chronicle_name} is partial")

            if gaps:
                logging.warn(
                    f"{chronicle_name} has gaps")

            # TODO: recover code for sake of seeing gaps
            # print()
            # print("Partial recordings:")
            # partial_recordings_by_day = {}
            # for detail in (d for d in details if is_partial_recording(d)):
            #     key = detail['start'].date()
            #     partial_recordings_by_day[key] = partial_recordings_by_day.get(
            #         key, []) + [detail]

            # for day, partial_recordings in partial_recordings_by_day.items():
            #     spans = [(d['start'], d['end']) for d in sorted(
            #         partial_recordings, key=lambda d: d['start'])]
            #     print(day)
            #     for span in spans:
            #         print(
            #             f"\t{span[0].time()} - {span[1].time()} (spans {int((span[1] - span[0]).total_seconds() // 60)}m)")

            # print()
            # print("Minutes of gaps:")
            # for detail in (d for d in details if is_skippy_recording(d)):
            #     print(detail['start'].date(), sum((d[1] - d[0]).total_seconds()
            #                                       for d in detail['gaps']) // 60)

            #     for gap_start, gap_end in detail['gaps'][:10]:
            #         print(
            #             f'\t{gap_start.time()} - {gap_end.time()} ({int((gap_end - gap_start).total_seconds() // 60) - 1}m missing)')
            #     if len(detail['gaps']) > 10:
            #         print('\t...')
