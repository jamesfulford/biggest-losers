import datetime
import typing


def main():
    from src.results import metadata, from_backtest
    from src import types, trading_day

    dt = typing.cast(datetime.datetime, trading_day.get_market_open_on_day(
        trading_day.get_last_market_close(trading_day.now())))
    previous_day = typing.cast(datetime.datetime, trading_day.get_market_open_on_day(
        trading_day.previous_trading_day(dt.date())))
    next_day = typing.cast(datetime.datetime, trading_day.get_market_open_on_day(
        trading_day.next_trading_day(dt.date())))

    from_backtest.write_results("trivial", [
        types.FilledOrder(intention=None, symbol='NRGU', quantity=1,
                          price=95, datetime=previous_day + datetime.timedelta(seconds=1)),
        types.FilledOrder(intention=None, symbol='NRGU', quantity=1,
                          price=105, datetime=dt + datetime.timedelta(minutes=7)),
        types.FilledOrder(intention=None, symbol='NRGU', quantity=-2,
                          price=120, datetime=next_day + datetime.timedelta(minutes=23)),
    ], metadata.Metadata(commit_id="", last_updated=datetime.datetime.now()))
