import datetime
import typing

from src import types, trading_day


def trades_by_day(trades: typing.Iterable[types.Trade]) -> typing.Iterator[typing.Tuple[datetime.date, list[types.Trade]]]:
    current_day = None
    trades_on_day = []
    for trade in trades:
        day = trade.get_end().date()
        if day != current_day:
            if current_day:
                yield current_day, trades_on_day
            current_day = day
            trades_on_day = []
        trades_on_day.append(trade)
    yield typing.cast(datetime.date, current_day), trades_on_day


def get_profit_usage_ratio(trades: typing.Iterable[types.Trade]) -> float:
    total_profit = sum(trade.get_profit_loss() for trade in trades)
    total_usage = sum(trade.get_value_spent() for trade in trades)
    return total_profit / total_usage if total_usage else 0


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("result_name", type=str)
    args = parser.parse_args()

    from src.results import read_results
    trades = list(read_results.get_trades(args.result_name))

    trade_days = dict(trades_by_day(trades))

    max_day_usage_day_trades_tuple = max(trade_days.items(), key=lambda day_trades_tuple: sum(
        t.get_value_spent() for t in day_trades_tuple[1]))

    # TODO: enhance metadata to have start and end days
    # TODO: enhance metadata to have params too (probably useful, but not in this file)
    # meta = read_results.get_metadata(args.result_name)
    for day in trading_day.generate_trading_days(trades[0].get_start().date(), trades[-1].get_end().date()):
        days_trades = trade_days.get(day, [])
        profit_usage_ratio = get_profit_usage_ratio(days_trades)
        print(f'{day} ({len(days_trades):>2}): {profit_usage_ratio:>6.1%}',
              f"{int(profit_usage_ratio * -100) * '=':>50}|{int(profit_usage_ratio * 100) * '=':<50}")

    print()
    print(f'{len(trades)} trades')

    total_profit = sum(trade.get_profit_loss() for trade in trades)
    total_usage = sum(trade.get_value_spent() for trade in trades)
    profit_usage_ratio = total_profit / total_usage if total_usage else 0
    print(f'{total_profit=:>+10.2f} {total_usage=:>+10.2f} {profit_usage_ratio=:>+10.2%}')

    max_day_usage_day = max_day_usage_day_trades_tuple[0]
    max_day_usage = sum(
        t.get_value_spent() for t in max_day_usage_day_trades_tuple[1])
    print(f'Maximum usage: {max_day_usage_day.isoformat()} {max_day_usage=}')

    # ROI depends on how the account is managed. profit_usage_ratio is an efficiency metric, not ROI.

    # TODO: consider more account simulator scripts that adjust quantities dynamically or even do an exponential approach
    # TODO: show simulation results via quantstat (cannot really do quantstat without a starting balance)

    # this is a bad assumption:
    account_balance = max_day_usage
    for day, trades_on_day in sorted(trade_days.items()):
        # arithmetic, not compounding:
        account_balance += sum(t.get_profit_loss() for t in trades_on_day)
        # print(f'{day.isoformat()} {account_balance:>+10.2f}')

    print(f"Raw ROI: {(account_balance / max_day_usage) - 1:>+10.2%} (initial: {max_day_usage:>+10.2f} final: {account_balance:>+10.2f})")
