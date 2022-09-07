from itertools import count


def main():
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument("result_name", type=str)

    args = parser.parse_args()

    from src.results import read_results

    trades = list(read_results.get_trades(args.result_name))

    # TODO: by day, by trade, other "play" groupings?
    # TODO: over time, chart (so we can see whether we are losing our edge)

    count_trades = len(trades)
    assert count_trades

    count_buy_orders = sum(sum(1 for o in t.orders if o.is_buy())
                           for t in trades)
    assert count_buy_orders == count_trades, "TODO: add support for multi-entry-order trades edge analysis"

    winners = [t for t in trades if t.is_win()]
    losers = [t for t in trades if not t.is_win()]

    win_rate = len(winners) / count_trades

    win_loss_ratio = sum(t.get_profit_loss() for t in winners) / - \
        sum(t.get_profit_loss() for t in losers)

    print(f"trades: {count_trades}")
    print(f"win rate: {win_rate:.1%}")
    print(f"win/loss ratio: {win_loss_ratio:.1f}")

    expected_value = sum(t.get_profit_loss() for t in trades) / count_trades
    overall_roi = (sum(t.get_value_extracted()
                       for t in trades) / sum(t.get_value_spent() for t in trades)) - 1
    biggest_win = max(trades, key=lambda t: t.get_profit_loss())
    biggest_loss = min(trades, key=lambda t: t.get_profit_loss())

    print(
        f"Expected value per trade: {expected_value:.2f} ({overall_roi:.1%})")
    # TODO: statistical test that we have an edge

    print(
        f"biggest win: {biggest_win.get_profit_loss():.2f} ({biggest_win.get_roi():.1%})")
    print(
        f"biggest loss: {biggest_loss.get_profit_loss():.2f} ({biggest_loss.get_roi():.1%})")

    kelly_percent = win_rate - ((1-win_rate) / win_loss_ratio)
    print(f"kelly criterion: {kelly_percent:.1%}")
