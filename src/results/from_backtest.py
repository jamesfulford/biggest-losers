import src.types as types

import src.results.dumping as dumping
import src.results.metadata as metadata
import src.results.crud as crud


def write_results(results_name: str, orders: list[types.FilledOrder], metadata: metadata.Metadata):
    try:
        crud.delete_result(results_name)
    except FileNotFoundError:
        pass
    crud.create_result(results_name)

    dumping.overwrite_metadata(results_name, metadata)
    dumping.overwrite_intention_filled_orders(results_name, orders)
