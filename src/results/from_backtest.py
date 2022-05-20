from src import types
from src.results import dumping, metadata, crud


def write_results(results_name: str, orders: list[types.FilledOrder], metadata: metadata.Metadata):
    try:
        crud.delete_result(results_name)
    except FileNotFoundError:
        pass
    crud.create_result(results_name)

    dumping.overwrite_metadata(results_name, metadata)
    dumping.overwrite_intention_filled_orders(results_name, orders)
