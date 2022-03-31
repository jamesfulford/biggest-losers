
from datetime import date, datetime
import json
import os
from typing import Iterable, Iterator, Optional, TypedDict, cast

from src.data.polygon.grouped_aggs import Ticker
from src.pathing import get_paths


def _read_jsonl_lines(path: str) -> Iterator[dict]:
    with open(path) as f:
        yield from (json.loads(line) for line in f)


class ChronicleEntry(TypedDict):
    now: datetime
    ticker: Ticker


#
# Recorded chronicle
#
def get_scanner_recorded_chronicle_path(scanner_name: str, day: date, commit_id: Optional[str] = None):
    if not commit_id:
        commit_id = os.environ.get("GIT_COMMIT", "dev")

    path = get_paths()['data']['dir']

    return os.path.join(
        path, 'chronicles', scanner_name, 'live', f'{day.isoformat()}-{commit_id}.jsonl')


def read_recorded_chronicle(scanner_name: str, day: date, commit_id: Optional[str] = None) -> Iterator[ChronicleEntry]:
    jsonl_feed = _read_jsonl_lines(
        get_scanner_recorded_chronicle_path(scanner_name, day, commit_id))
    feed = ({
        "now": datetime.strptime(entry['now'], "%Y-%m-%dT%H:%M:%S%z"),
        "ticker": entry['ticker']
    } for entry in jsonl_feed)
    return cast(Iterator[ChronicleEntry], feed)


#
# Reconstructed chronicle
#
class HistoricalChronicleEntry(ChronicleEntry):
    true_ticker: Ticker


def get_scanner_backtest_chronicle_path(scanner: str, cache_built_date: date, commit_id: Optional[str] = None) -> str:
    if not commit_id:
        commit_id = os.environ.get("GIT_COMMIT", "dev")

    path = get_paths()['data']['dir']

    return os.path.join(
        path, 'chronicles', scanner, 'backtest', f'{cache_built_date.isoformat()}-{commit_id}.jsonl')


def read_backtest_chronicle(scanner: str, cache_built_date: date, commit_id: Optional[str] = None) -> Iterator[HistoricalChronicleEntry]:
    jsonl_feed = _read_jsonl_lines(
        get_scanner_backtest_chronicle_path(scanner, cache_built_date, commit_id))
    feed = ({
        "now": datetime.strptime(entry['now'], "%Y-%m-%dT%H:%M:%S%z"),
        "ticker": entry['ticker'],
        "true_ticker": entry['true_ticker'],
    } for entry in jsonl_feed)
    return cast(Iterator[HistoricalChronicleEntry], feed)


#
#
#
def batch_by_minute(iterable: Iterable[ChronicleEntry]) -> Iterator[list[ChronicleEntry]]:
    """
    Split the given iterable into batches of size 60.
    """
    previous_time = None
    batch = []
    for entry in iterable:
        if not previous_time:
            previous_time = entry['now']

        if previous_time != entry['now']:
            yield sorted(batch, key=lambda e: e['ticker']['T'])
            batch = []
            previous_time = entry['now']

        batch.append(entry)

    if batch:
        yield batch
