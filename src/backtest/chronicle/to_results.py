import datetime
import itertools
import os
import typing
from src.backtest.chronicle import crud, types as chronicle_types
from src import types
from src.results import from_backtest, metadata


def chunk_feed_by_day_grouped_by_symbol(chronicle_feed: typing.Iterator[chronicle_types.Snapshot]) -> typing.Iterator[typing.Tuple[datetime.date, typing.Dict[str, typing.List[chronicle_types.ChronicleEntry]]]]:
    first_snapshot = next(chronicle_feed)

    day = first_snapshot.now.date()
    tickers_on_day = {}

    for snapshot in itertools.chain([first_snapshot], chronicle_feed):
        snapshot_day = snapshot.now.date()
        if day != snapshot_day:
            yield day, tickers_on_day
            tickers_on_day = {}
            day = snapshot_day

        for entry in snapshot.entries:
            symbol = entry.ticker['T']
            tickers_on_day[symbol] = tickers_on_day.get(symbol, []) + [entry]


def main():
    # TODO: why skipping second/last day on solarsail-1?
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument("chronicle_name", type=str)
    parser.add_argument("result_name", type=str)

    args = parser.parse_args()

    chronicle_name = args.chronicle_name
    result_name = args.result_name

    chronicle = crud.get(chronicle_name)
    from_backtest.write_results(result_name, list(chunk_feed_into_signals_by_span(
        iter(chronicle.snapshots))), metadata.Metadata(commit_id=os.environ.get("GIT_COMMIT", 'dev'), last_updated=datetime.datetime.now()))


def chunk_feed_into_signals_by_span(chronicle_feed: typing.Iterator[chronicle_types.Snapshot]) -> typing.Iterable[types.FilledOrder]:
    for day, tickers_on_day in chunk_feed_by_day_grouped_by_symbol(chronicle_feed):
        print(day, tickers_on_day.keys())

        for symbol, entries in tickers_on_day.items():

            previous_time = entries[0].now
            yield types.FilledOrder(
                intention=types.Intention(symbol=symbol, datetime=previous_time, extra={
                                          'ticker': entries[0].ticker}),
                symbol=symbol,
                datetime=previous_time,
                price=entries[0].ticker['c'],
                quantity=1,
            )
            for entry in entries:
                if entry.now - previous_time > datetime.timedelta(minutes=1):
                    yield types.FilledOrder(
                        intention=types.Intention(symbol=symbol, datetime=previous_time, extra={
                                                  'ticker': entry.ticker}),
                        symbol=symbol,
                        datetime=previous_time,
                        price=entry.ticker['c'],
                        quantity=-1,
                    )
                    yield types.FilledOrder(
                        intention=types.Intention(symbol=symbol, datetime=entry.now, extra={
                                                  'ticker': entry.ticker}),
                        symbol=symbol,
                        datetime=entry.now,
                        price=entry.ticker['c'],
                        quantity=1,
                    )
                previous_time = entry.now
            yield types.FilledOrder(
                intention=types.Intention(symbol=symbol, datetime=previous_time, extra={
                                          'ticker': entries[-1].ticker}),
                symbol=symbol,
                datetime=previous_time,  # TODO: timestamps are saying 16:00, maybe should be 15:59?
                price=entries[-1].ticker['c'],
                quantity=-1,
            )
