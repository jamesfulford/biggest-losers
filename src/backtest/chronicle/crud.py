import os
import shutil
import typing
from src.backtest.chronicle import types
from src.outputs import pathing, json_dump, jsonl_dump


def get(chronicle_name: str) -> types.Chronicle:
    paths = pathing.get_chronicle_folder_paths(chronicle_name)

    metadata = types.ChronicleMeta.from_dict(
        json_dump.read_json(paths['metadata.json']))
    snapshots = [types.Snapshot.from_dict(
        l) for l in jsonl_dump.read_jsonl_lines(paths['snapshots.jsonl'])]

    return types.Chronicle.from_data(snapshots, metadata)


def delete(chronicle_name: str):
    paths = pathing.get_chronicle_folder_paths(chronicle_name)
    path = paths['dir']

    shutil.rmtree(path)


def create(chronicle_name: str, metadata: types.ChronicleMeta):
    paths = pathing.get_chronicle_folder_paths(chronicle_name)
    path = paths['dir']

    os.mkdir(path)

    json_dump.write_json(paths['metadata.json'], metadata.to_dict())


def list() -> list[str]:
    paths = pathing.get_paths()
    path = paths['data']['chronicles']['dir']

    return [
        p for p in os.listdir(path) if not p.startswith(".")
    ]


def append_snapshots(chronicle_name: str, snapshots: typing.Iterable[types.Snapshot]):
    paths = pathing.get_chronicle_folder_paths(chronicle_name)

    jsonl_dump.append_jsonl(paths['snapshots.jsonl'], (
        snapshot.to_dict() for snapshot in snapshots
    ))
