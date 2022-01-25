
from datetime import date
from typing import Callable


def enrich_tickers_with_asset_class(day: date, tickers: list[dict], classes: dict[str, Callable]):
    """
    Adds keys of `classes` to each ticker in `tickers`.
    Ticker is skipped if no classes evaluate to true.
    Each class evaluator is passed the ticker and the day.
    """
    for ticker in tickers:
        for asset_class_name, is_asset_class in classes.items():
            ticker[asset_class_name] = is_asset_class(ticker["T"], day=day)

        if not any(ticker[name] for name in classes.keys()):
            continue

        yield ticker
