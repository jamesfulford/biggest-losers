from collections.abc import MutableMapping
from datetime import date, datetime
import logging
import os
from typing import Iterable, Tuple, TypedDict
from src.backtest.chronicle.read import ChronicleEntry, batch_by_minute, read_backtest_chronicle, read_chronicle
from src.csv_dump import write_csv
from src.pathing import get_paths


def collect_scanner_ticker_spans(feed: Iterable[ChronicleEntry]) -> Iterable[Tuple[ChronicleEntry, datetime]]:
    class State(TypedDict):
        entry: ChronicleEntry
        last_update: datetime

    state: dict[str, State] = {}

    for records in batch_by_minute(feed):
        current_time = records[0]['now']

        for record in records:
            symbol = record['ticker']['T']

            state[symbol] = state.get(symbol, {
                "entry": record,
                "last_update": current_time,
            })
            state[symbol]['last_update'] = current_time

        for symbol, symbol_state in list(state.items()):
            if symbol_state['last_update'] != current_time:
                # fell off the scanner (wasn't updated this time)
                yield symbol_state['entry'], current_time
                del state[symbol]


# https://www.freecodecamp.org/news/how-to-flatten-a-dictionary-in-python-in-4-different-ways/
def _flatten_dict_gen(d, parent_key, sep):
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            yield from flatten_dict(v, new_key, sep=sep).items()
        else:
            yield new_key, v


def flatten_dict(d: MutableMapping, parent_key: str = '', sep: str = '.'):
    return dict(_flatten_dict_gen(d, parent_key, sep))


def main():

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('scanner_name', type=str)
    parser.add_argument('chronicle_type', type=str,
                        choices=['recorded', 'backtest'])
    parser.add_argument('chronicle_date', type=str)
    parser.add_argument('chronicle_name', type=str)

    args = parser.parse_args()
    scanner_name = args.scanner_name
    chron_type = args.chronicle_type
    chronicle_date = date(*[int(i) for i in args.chronicle_date.split('-')])
    chronicle_name = args.chronicle_name

    path = os.path.join(
        get_paths()['data']['outputs']['dir'], scanner_name + ".scanner.csv")

    logging.info(
        f"Writing csv for {scanner_name} {chron_type} {chronicle_date} {chronicle_name}...")

    backtest_feed = read_chronicle(
        scanner_name, chron_type, chronicle_date, chronicle_name)
    span_feed = collect_scanner_ticker_spans(backtest_feed)
    csv_feed = ({
        "entry_time": entry['now'],
        "exit_time": exit_time,
        "duration": str(exit_time - entry['now']),
        "is_overnight": exit_time.date() != entry['now'].date(),
        "entry": entry['ticker'],
    } for entry, exit_time in span_feed)
    flat_csv_feed = (flatten_dict(row) for row in csv_feed)
    lines_written = write_csv(path, flat_csv_feed, [
        'entry_time', 'exit_time', 'is_overnight', 'duration', 'entry.T'])

    logging.info(
        f"Done writing csv for {scanner_name} {chron_type} {chronicle_date} {chronicle_name}. Wrote {lines_written} rows.")
