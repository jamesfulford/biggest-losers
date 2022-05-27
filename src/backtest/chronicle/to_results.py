import datetime
import itertools
import typing
from src.backtest.chronicle import read
from src import types
from src.results import from_backtest, metadata


def chunk_feed_by_day_grouped_by_symbol(chronicle_feed):
    first_entry = next(chronicle_feed)

    day = first_entry['now'].date()
    tickers_on_day = {}

    for entry in itertools.chain([first_entry], chronicle_feed):
        entry_day = entry['now'].date()
        if day != entry_day:
            yield day, tickers_on_day
            tickers_on_day = {}
            day = entry_day

        symbol = entry['ticker']['T']
        tickers_on_day[symbol] = tickers_on_day.get(symbol, []) + [entry]


def main():
    import argparse
    parser = argparse.ArgumentParser()

    # TODO: name chronicles by custom names, not by scanner name+date+commit, so awkward to work with
    parser.add_argument("scanner_name", type=str)
    parser.add_argument('chronicle_type', type=str,
                        choices=['recorded', 'backtest'])
    parser.add_argument("day", type=str)
    parser.add_argument("commit", type=str)
    parser.add_argument("result_name", type=str)

    args = parser.parse_args()

    scanner_name = args.scanner_name
    chron_type = args.chronicle_type
    day = datetime.date.fromisoformat(args.day)
    commit = args.commit

    chronicle_feed = read.read_chronicle(scanner_name, chron_type, day, commit)
    from_backtest.write_results(args.result_name, list(chunk_feed_into_signals_by_span(
        chronicle_feed)), metadata.Metadata(commit_id=commit, last_updated=datetime.datetime.now()))


def chunk_feed_into_signals_by_span(chronicle_feed: typing.Iterable[read.ChronicleEntry]) -> typing.Iterable[types.FilledOrder]:
    for day, tickers_on_day in chunk_feed_by_day_grouped_by_symbol(chronicle_feed):
        print(day, tickers_on_day.keys())

        for symbol, entries in tickers_on_day.items():

            previous_time = entries[0]['now']
            yield types.FilledOrder(
                intention=types.Intention(symbol=symbol, datetime=previous_time, extra={
                                          'ticker': entries[0]['ticker']}),
                symbol=symbol,
                datetime=previous_time,
                price=entries[0]['ticker']['c'],
                quantity=1,
            )
            for entry in entries:
                if entry['now'] - previous_time > datetime.timedelta(minutes=1):
                    yield types.FilledOrder(
                        intention=types.Intention(symbol=symbol, datetime=previous_time, extra={
                                                  'ticker': entry['ticker']}),
                        symbol=symbol,
                        datetime=previous_time,
                        price=entry['ticker']['c'],
                        quantity=-1,
                    )
                    yield types.FilledOrder(
                        intention=types.Intention(symbol=symbol, datetime=entry['now'], extra={
                                                  'ticker': entry['ticker']}),
                        symbol=symbol,
                        datetime=entry['now'],
                        price=entry['ticker']['c'],
                        quantity=1,
                    )
                previous_time = entry['now']
            yield types.FilledOrder(
                intention=types.Intention(symbol=symbol, datetime=previous_time, extra={
                                          'ticker': entries[-1]['ticker']}),
                symbol=symbol,
                datetime=previous_time,  # TODO: timestamps are saying 16:00, maybe should be 15:59?
                price=entries[-1]['ticker']['c'],
                quantity=-1,
            )
