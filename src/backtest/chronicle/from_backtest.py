
import typing

from src.backtest.chronicle import crud, types


def write_snapshots(chronicle_name: str, snapshots: typing.Iterable[types.Snapshot], metadata: types.ChronicleMeta):
    try:
        crud.delete(chronicle_name)
    except FileNotFoundError:
        pass

    crud.create(chronicle_name, metadata)
    crud.append_snapshots(chronicle_name, snapshots)
