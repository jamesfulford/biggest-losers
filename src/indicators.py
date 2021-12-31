
def calculate_true_range(candle, prior_candle):
    """
    Calculates the true range.
    """
    return max(candle["h"], prior_candle["c"]) - min(candle["l"], prior_candle["c"])


def ema_of(values):
    """
    Returns emas of a list of values (reads values left to right)
    """
    n = len(values)

    ema = []
    ema.append(sum(values) / n)

    for v in values[1:]:
        ema.append((v + ((n - 1) * ema[-1])) / n)

    return ema


def current_sma_of(values):
    """
    Returns sma of a list of values (order doesn't matter)
    """
    n = len(values)
    s = sum(values)
    return s / n


def atr_of(candles):
    """
    Returns a list of average true range values. Last should be most recent.
    """
    true_ranges = []
    for i in range(1, len(candles)):
        true_ranges.append(calculate_true_range(candles[i], candles[i - 1]))

    return ema_of(true_ranges)


if __name__ == "__main__":
    print(atr_of([
        {
            "h": 10,
            "l": 5,
            "c": 7,
        },
        {
            "h": 10,
            "l": 5,
            "c": 6,
        },
        {
            "h": 7,
            "l": 3,
            "c": 3,
        },
        {
            "h": 7,
            "l": 5,
            "c": 7,
        },
        {
            "h": 3,
            "l": 1,
            "c": 2,
        },
    ]))
