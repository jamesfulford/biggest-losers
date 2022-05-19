import dataclasses
import datetime


@dataclasses.dataclass
class Summary():
    start: datetime.date
    end: datetime.date

    roi: float
    # TODO: add more key stats for comparison of results

    def to_dict(self):
        return {
            "start": self.start,
            "end": self.end,

            "roi": self.roi
        }

    @staticmethod
    def from_dict(d):
        return Summary(
            start=d["start"],
            end=d["end"],

            roi=d["roi"]
        )
