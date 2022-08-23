import logging
import typing
import datetime
from src.scripts.helpers.parse_period import add_range_args, interpret_args
from src.data.polygon import get_candles
from src.results import metadata, from_backtest
from src import trading_day, types


def main():
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument("symbol", type=str)
    add_range_args(parser, required=False)

    args = parser.parse_args()

    symbol = typing.cast(str, args.symbol).upper().strip()
    start, end = interpret_args(args)

    candles = get_candles.get_d_candles(symbol, start, end)
    if not candles:
        logging.warning(
            f"Could not get candles for {symbol} between {start} and {end}")
        return

    name = f'{symbol}-from-{start}-to-{end}'
    print(name)
    from_backtest.write_results(name, [
        types.FilledOrder(intention=None,
                          symbol=symbol,
                          quantity=1,
                          price=candles[0]['open'],
                          datetime=trading_day.get_last_market_open(datetime.datetime.combine(candles[0]['date'], datetime.time(9, 30)))),
        types.FilledOrder(intention=None,
                          symbol=symbol,
                          quantity=-1,
                          price=candles[-1]['close'],
                          datetime=trading_day.get_last_market_close(datetime.datetime.combine(candles[-1]['date'], datetime.time(16, 0))))
    ], metadata.from_context(__file__, start, end, {
        "symbol": symbol,
    }))
