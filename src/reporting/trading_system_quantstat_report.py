import datetime
import typing
import quantstats
import pandas as pd

from src.reporting.trades import Trade, read_trades


def trades_by_day(trades: typing.Iterator[Trade]) -> typing.Iterator[typing.Tuple[datetime.date, typing.List[Trade]]]:
    current_day = None
    trades_on_day = []
    for trade in trades:
        day = trade['closed_at'].date()
        if day != current_day:
            if current_day:
                yield current_day, trades_on_day
            current_day = day
            trades_on_day = []
        trades_on_day.append(trade)
    yield typing.cast(datetime.date, current_day), trades_on_day


def daily_rois(trades: typing.Iterator[Trade]) -> typing.Iterator[typing.Tuple[datetime.date, float]]:
    # how much money made on day for amount of money used
    for day, trades_on_day in trades_by_day(trades):
        # `abs` here because bought_cost is negative for short/put trades
        yield day, sum(trade['profit_loss'] for trade in trades_on_day) / sum(abs(trade['bought_cost']) for trade in trades_on_day) if trades_on_day else 0


def main():
    # TODO: cli
    input_path = "/Users/jamesfulford/Downloads/options_trades.jsonl"

    trades = list(read_trades(input_path))
    rois = list(daily_rois(iter(trades)))
    for day, roi in rois:
        print(f'{day}: {roi:>6.1%}',
              f"{int(roi * -200) * '=':>30}|{int(roi * 200) * '=':<30}")

    print()
    print(f'{len(trades)} trades')
    print(f'{sum(t["profit_loss"] for t in trades)} profit/loss total ({sum(t["profit_loss"] for t in trades) / len(rois)})')
    print(f'{sum(abs(t["bought_cost"]) for t in trades)} bought cost total ({sum(abs(t["bought_cost"]) for t in trades) / len(rois)} / day, max {max(abs(t["bought_cost"]) for t in trades)})')

    # roi = sum(trade['profit_loss'] for trade in trades) / \
    #     sum(abs(trade['bought_cost']) for trade in trades) if trades else 0
    # print(" " * 18, f"{int(roi * -200) * '=':>30}|{int(roi * 200) * '=':<30}")

    # s = pd.Series(r for _, r in rois)
    # s.index = pd.DatetimeIndex(d for d, _ in rois)

    # print(quantstats.reports.basic(s))
