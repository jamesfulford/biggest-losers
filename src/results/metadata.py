import dataclasses
import datetime


@dataclasses.dataclass
class Metadata():
    commit_id: str
    last_updated: datetime.datetime

    # TODO: add more info

    def to_dict(self):
        return {
            "commit_id": self.commit_id,
            "last_updated": self.last_updated,
        }

    @staticmethod
    def from_dict(d):
        return Metadata(commit_id=d['commit_id'], last_updated=d['last_updated'])
