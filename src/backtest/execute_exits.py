from collections import Counter
import datetime
import typing
from src.backtest import exiters
from src.data.finnhub.finnhub import get_1m_candles
from src.data.polygon.get_option_candles import get_option_candles
from src.data.polygon.option_chain import extract_contract_specifier_from_polygon_option_ticker
from src.data.types.candles import Candle, CandleIntraday
from src import types, trading_day


def execute_exiter(candles: list[Candle], exiter: exiters.Exiter) -> typing.Tuple[typing.Optional[float], Candle]:
    """
    Returns sell_price and candle sold on
    If no sale occurred, returns None, and last candle in candles
    """

    for candle in candles:
        price = exiter.observe(candle)
        if price is not None:
            return price, candle
    return None, candles[-1]


def symbol_is_option(symbol: str) -> bool:
    try:
        extract_contract_specifier_from_polygon_option_ticker(symbol)
        return True
    except ValueError:
        return False


def get_candles_for_backtest(symbol: str, start: datetime.datetime, end: datetime.datetime) -> list[CandleIntraday]:
    if symbol_is_option(symbol):
        candles = get_option_candles(extract_contract_specifier_from_polygon_option_ticker(
            symbol), '1', start.date(), end.date())
    else:
        candles = get_1m_candles(symbol, start.date(), end.date())

    if not candles:
        raise Exception("No candles found for {}".format(symbol))
    return extract_candles_in_range(candles, start, end)


def extract_candles_in_range(candles: list[CandleIntraday], start: datetime.datetime, end: datetime.datetime) -> list[CandleIntraday]:
    entry_candle = next(c for c in reversed(
        candles) if c['datetime'] <= start)
    exit_candle = next((c for c in candles if c['datetime'] >= end), None)
    if exit_candle is None:
        exit_candle = candles[-1]
    holding_candles = [
        c for c in candles if c['datetime'] >= entry_candle['datetime'] and c['datetime'] <= exit_candle['datetime']]
    return holding_candles


def find_exit_within_trade_timeframe(trade: types.Trade, exiter: exiters.Exiter) -> types.Trade:
    start, end, symbol = trade.get_start(), trade.get_end(), trade.get_symbol()
    candles = get_candles_for_backtest(symbol, start, end)
    sell_price, last_candle = execute_exiter(
        typing.cast(list[Candle], candles), exiter)
    last_candle = typing.cast(CandleIntraday, last_candle)
    closed_at = last_candle['datetime']

    if not sell_price:
        # Default to trade typical exit
        sell_price = trade.get_average_exit_price()

    # TODO: how to not do virtual orders with brackets?
    original_entry_virtual_order, _original_exit_virtual_order = trade.get_virtual_orders()
    return types.Trade(orders=[
        original_entry_virtual_order,
        types.FilledOrder(
            intention=None,
            symbol=trade.get_symbol(),
            price=sell_price,
            quantity=-trade.get_quantity(),
            datetime=closed_at,
        )])


def find_exit_within_trade_day(trade: types.Trade, exiter: exiters.Exiter) -> types.Trade:
    start, symbol = trade.get_start(), trade.get_symbol()
    end = typing.cast(
        datetime.datetime, trading_day.get_market_close_on_day(trade.get_end().date()))

    candles = get_candles_for_backtest(symbol, start, end)
    exiter.prime(candles[0])
    sell_price, last_candle = execute_exiter(
        typing.cast(list[Candle], candles), exiter)
    last_candle = typing.cast(CandleIntraday, last_candle)
    closed_at = last_candle['datetime']

    if not sell_price:
        # exit on last candle
        sell_price = candles[-1]['open']

    # TODO: how to not do virtual orders with brackets?
    original_entry_virtual_order, _original_exit_virtual_order = trade.get_virtual_orders()
    return types.Trade(orders=[
        original_entry_virtual_order,
        types.FilledOrder(
            intention=None,
            symbol=trade.get_symbol(),
            price=sell_price,
            quantity=-trade.get_quantity(),
            datetime=closed_at,
        )])


def build_exiter(context_trade: types.Trade) -> exiters.Exiter:
    # TODO: read from args
    # entry_price = context_trade.get_average_entry_price()
    return exiters.StopLossTrailingFixedOffsetExiter(1)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("result_name", type=str)
    parser.add_argument("output_result_name", type=str)
    args = parser.parse_args()

    assert args.result_name != args.output_result_name, "result_name and output_result_name must be different"

    from src.results import read_results

    trades = read_results.get_trades(args.result_name)

    # TODO: resolve this issue
    # Finnhub does not allow going back too far
    trades = [t for t in trades if t.get_start().date() > datetime.date.today(
    ) - datetime.timedelta(days=364)]

    print(f"Base stats:")
    print(f"  win/loss: {Counter(trade.is_win() for trade in trades)}")
    print(f"  profit:   {sum(t.get_profit_loss() for t in trades):.2f}")

    brack_trades = []
    for trade in trades:
        exiter = build_exiter(trade)
        brack_trades.append(find_exit_within_trade_day(trade, exiter))

    print(f"New stats:")
    print(f"  win/loss: {Counter(trade.is_win() for trade in brack_trades)}")
    print(f"  profit:   {sum(t.get_profit_loss() for t in brack_trades):.2f}")

    bracketed_orders = []
    for bracketed_trade in brack_trades:
        bracketed_orders.extend(bracketed_trade.orders)

    from src.results import from_backtest, metadata

    from_backtest.write_results(args.output_result_name, bracketed_orders, metadata.Metadata(
        commit_id="", last_updated=datetime.datetime.now()))
