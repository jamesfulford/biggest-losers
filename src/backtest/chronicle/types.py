
import dataclasses
import datetime

from src.data.polygon.grouped_aggs import Ticker


@dataclasses.dataclass
class ChronicleEntry:
    now: datetime.datetime
    ticker: Ticker

    def to_dict(self) -> dict:
        return {
            "now": self.now,
            "ticker": self.ticker,
        }

    @staticmethod
    def from_dict(d: dict):
        return ChronicleEntry(now=d["now"], ticker=d["ticker"])


@dataclasses.dataclass
class Snapshot:
    now: datetime.datetime
    entries: list[ChronicleEntry]

    def to_dict(self) -> dict:
        return {
            "now": self.now,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @staticmethod
    def from_dict(d: dict):
        return Snapshot(entries=[ChronicleEntry.from_dict(entry) for entry in d["entries"]], now=d["now"])


@dataclasses.dataclass
class ChronicleMeta:
    start: datetime.date
    end: datetime.date
    classification: str  # recorded, backtest
    origin: str  # scanner
    commit: str

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "classification": self.classification,
            "origin": self.origin,
            'commit': self.commit,
        }

    @staticmethod
    def from_dict(d: dict):
        return ChronicleMeta(
            start=datetime.date.fromisoformat(d["start"]),
            end=datetime.date.fromisoformat(d["end"]),
            classification=d["classification"],
            origin=d["origin"],
            commit=d["commit"],
        )

    def is_recorded(self) -> bool:
        return self.classification == "recorded"

    def is_backtest(self) -> bool:
        return self.classification == "backtest"


@dataclasses.dataclass
class Chronicle:
    snapshots: list[Snapshot]
    metadata: ChronicleMeta

    def to_dict(self) -> dict:
        return {
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
        }

    @staticmethod
    def from_data(snapshots: list[Snapshot], metadata: ChronicleMeta):
        return Chronicle(snapshots=snapshots, metadata=metadata)
