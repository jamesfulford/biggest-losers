from typing import Callable


def rank_candidates_by(tickers, criteria: Callable):
    tickers = sorted(tickers, key=criteria)
    for ticker in tickers:
        ticker['rank'] = tickers.index(ticker) + 1
    return tickers
