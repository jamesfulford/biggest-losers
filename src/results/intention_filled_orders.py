import logging
import src.results.dumping as dumping
import src.types as types


def enhance_order_with_intention(order: types.FilledOrder, intentions: list[types.Intention]) -> types.FilledOrder:
    intention = types.FilledOrder.find_matching_intention(order, intentions)
    if intention is not None:
        if order.intention:
            # TODO: merge the intentions together
            logging.warning(
                "Observed multiple intentions for the same order! Keeping the original one.")
        else:
            order.intention = intention
    return order


def update(result_name: str):
    logging.info(
        f"Updating intention_filled_orders.jsonl for {result_name}...")
    intentions = list(dumping.read_intentions(result_name))

    dumping.overwrite_intention_filled_orders(result_name, [enhance_order_with_intention(
        order, intentions) for order in dumping.read_orders(result_name)])
    logging.info(
        f"Done updating intention_filled_orders.jsonl for {result_name}.")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('result_name', type=str)
    args = parser.parse_args()

    update(args.result_name)
