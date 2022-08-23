import dataclasses
import datetime
import os
import typing
from src import trading_day


def from_context(dunder_file__: str, start: datetime.date, end: datetime.date, params: dict[str, typing.Any]):
    return Metadata(
        commit_id=os.environ.get("GIT_COMMIT", ""),
        last_updated=trading_day.now(),
        source_file_path=dunder_file__,
        start=start,
        end=end,
        params=params,
    )


@dataclasses.dataclass
class Metadata():
    commit_id: str
    last_updated: datetime.datetime
    source_file_path: str
    start: datetime.date
    end: datetime.date
    params: dict[str, typing.Any]

    def to_dict(self):
        return {
            "commit_id": self.commit_id,
            "last_updated": self.last_updated,
            "source_file_path": self.source_file_path,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "params": self.params,
        }

    @staticmethod
    def from_dict(d):
        return Metadata(
            commit_id=d['commit_id'],
            last_updated=d['last_updated'],
            source_file_path=d['source_file_path'],
            start=datetime.date.fromisoformat(d['start']),
            end=datetime.date.fromisoformat(d['end']),
            params=d['params'],
        )
