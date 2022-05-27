# TODO: rebuild this to use the new chronicle class

# from datetime import date
# import logging
# from typing import Iterable, Iterator, Tuple
# from itertools import chain

# from src.backtest.chronicle.read import ChronicleEntry, batch_by_minute, read_backtest_chronicle, read_recorded_chronicle

# def batch_by_minute(iterable: Iterable[ChronicleEntry]) -> Iterator[list[ChronicleEntry]]:
#     """
#     Split the given iterable into batches of size 60.
#     """
#     previous_time = None
#     batch = []
#     for entry in iterable:
#         if not previous_time:
#             previous_time = entry['now']

#         if previous_time != entry['now']:
#             yield sorted(batch, key=lambda e: e['ticker']['T'])
#             batch = []
#             previous_time = entry['now']

#         batch.append(entry)

#     if batch:
#         yield batch


# def batch_by_minute_and_link_feeds(feed1: Iterable[ChronicleEntry], feed2: Iterable[ChronicleEntry]) -> Iterator[Tuple[list[ChronicleEntry], list[ChronicleEntry]]]:
#     # Batch by minute
#     batched_feed_1, batched_feed_2 = batch_by_minute(
#         feed1), batch_by_minute(feed2)
#     batch_1, batch_2 = next(batched_feed_1, None), next(batched_feed_2, None)

#     # Syncronize scroll through batches
#     while True:
#         if batch_1 is None or batch_2 is None:
#             break
#         now_1, now_2 = batch_1[0]['now'], batch_2[0]['now']

#         if now_1 < now_2:
#             logging.warning(f"NOTE: feed2 is missing {now_1}")
#             batch_1 = next(batched_feed_1, None)
#             continue
#         if now_1 > now_2:
#             logging.warning(f"NOTE: feed1 is missing {now_2}")
#             batch_2 = next(batched_feed_2, None)
#             continue

#         yield batch_1, batch_2

#         batch_1, batch_2 = next(
#             batched_feed_1, None), next(batched_feed_2, None)


# def main():
#     # TODO: choose chronicles from command line
#     scanner_name = "meemaw"

#     live_chronicle_feed = read_recorded_chronicle(
#         scanner_name, date(2022, 3, 22), "dev")
#     backtest_chronicle_feed = read_backtest_chronicle(
#         scanner_name, date(2022, 3, 22), "dev")

#     # Scroll feeds to the same time
#     live_entry = next(live_chronicle_feed)
#     backtest_entry = next(backtest_chronicle_feed)
#     while True:
#         live_now = live_entry['now']
#         backtest_now = backtest_entry['now']
#         if live_now == backtest_now:
#             break
#         elif live_now < backtest_now:
#             live_entry = next(live_chronicle_feed)
#             continue
#         elif live_now > backtest_now:
#             backtest_entry = next(backtest_chronicle_feed)
#             continue

#     for live_batch, backtest_batch in batch_by_minute_and_link_feeds(chain([live_entry], live_chronicle_feed), chain([backtest_entry], backtest_chronicle_feed)):
#         live_symbols = set(e['ticker']['T'] for e in live_batch)
#         backtest_symbols = set(e['ticker']['T'] for e in backtest_batch)

#         missing_in_bt = live_symbols.difference(
#             backtest_symbols)
#         missing_in_live = backtest_symbols.difference(live_symbols)
#         if missing_in_bt or missing_in_live:
#             logging.warning(
#                 f"Symbol mismatch! {live_batch[0]['now']} {missing_in_bt=} {missing_in_live=}")
#             # for symbol in missing_in_live:
#             #     backtest_ticker = next(
#             #         filter(lambda t: t['ticker']['T'] == symbol, backtest_batch))
#             #     pprint(backtest_ticker)
#             # for symbol in missing_in_bt:
#             #     live_ticker = next(
#             #         filter(lambda t: t['ticker']['T'] == symbol, live_batch))
#             #     pprint(live_ticker)

#             # TODO: to allow checking why BT is acting differently,
#             # run backtest_on_day with just that minute
#             # and return more tickers? (raise min_n? or something)

#         shared_symbols = live_symbols.intersection(backtest_symbols)

#         # TODO: find changes in order
#         live_filtered_batch = [
#             t for t in live_batch if t['ticker']['T'] in shared_symbols]
#         live_filtered_batch.sort(key=lambda t: t['ticker']['T'])
#         backtest_filtered_batch = [
#             t for t in backtest_batch if t['ticker']['T'] in shared_symbols]
#         backtest_filtered_batch.sort(key=lambda t: t['ticker']['T'])

#         for live_entry, backtest_entry in zip(live_filtered_batch, backtest_filtered_batch):
#             assert live_entry['ticker']['T'] == backtest_entry['ticker']['T']

#             open_ratio = live_entry['ticker']['o'] / \
#                 (backtest_entry['ticker']['o'])
#             if open_ratio > 1.05 or open_ratio < 0.95:
#                 logging.info(
#                     f"open mismatch T={live_entry['ticker']['T']} @ {live_entry['now']} live={live_entry['ticker']['o']} backtest={backtest_entry['ticker']['o']} ratio={open_ratio:.2f}")

#             high_ratio = live_entry['ticker']['h'] / \
#                 (backtest_entry['ticker']['h'])
#             if high_ratio > 1.05 or high_ratio < 0.95:
#                 logging.info(
#                     f"high mismatch T={live_entry['ticker']['T']} @ {live_entry['now']} live={live_entry['ticker']['h']} backtest={backtest_entry['ticker']['h']} ratio={high_ratio:.2f}")

#             low_ratio = live_entry['ticker']['l'] / \
#                 (backtest_entry['ticker']['l'])
#             if low_ratio > 1.05 or low_ratio < 0.95:
#                 logging.info(
#                     f"low mismatch T={live_entry['ticker']['T']} @ {live_entry['now']} live={live_entry['ticker']['l']} backtest={backtest_entry['ticker']['l']} ratio={low_ratio:.2f}")

#             close_ratio = live_entry['ticker']['c'] / \
#                 (backtest_entry['ticker']['c'])
#             if close_ratio > 1.05 or close_ratio < 0.95:
#                 logging.info(
#                     f"close mismatch T={live_entry['ticker']['T']} @ {live_entry['now']} live={live_entry['ticker']['c']} backtest={backtest_entry['ticker']['c']} ratio={close_ratio:.2f}")

#             # NOTE: 1m candle reconstructions are known to be lower than the actual volume
#             volume_ratio = live_entry['ticker']['v'] / \
#                 (backtest_entry['ticker']['v'] + 1)
#             if volume_ratio > 1.01:
#                 logging.info(
#                     f"volume mismatch T={live_entry['ticker']['T']} @ {live_entry['now']} live={live_entry['ticker']['v']} backtest={backtest_entry['ticker']['v']} ratio={volume_ratio:.2f}")
