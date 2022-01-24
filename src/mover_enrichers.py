from datetime import date
from src.data.polygon.grouped_aggs import get_last_2_candles, get_last_n_candles
from src.indicators import atr_of, current_sma_of, ema_of


def enrich_mover(mover):
    ticker = mover["mover_day_of_action"]["T"]
    day_of_action = mover["day_of_action"]

    for interesting_ticker in ["SPY"]:
        changes = get_ticker_changes(
            day_of_action, interesting_ticker=interesting_ticker)

        mover[f"{interesting_ticker.lower()}_day_of_action_percent_change"] = changes["close_to_close_percent_change"]
        mover[f"{interesting_ticker.lower()}_day_of_action_intraday_percent_change"] = changes["close_to_open_percent_change"]

    mover[f"100sma"] = get_sma(ticker, day_of_action, 100)  # S!!!

    mover[f"100ema"] = get_ema(ticker, day_of_action, 100)
    mover[f"50ema"] = get_ema(ticker, day_of_action, 50)

    mover[f"14atr"] = get_atr(ticker, day_of_action, 14)

    return mover


def get_ema(ticker: str, day_of_action: date, n: int, field='c'):
    candles = get_last_n_candles(day_of_action, ticker, n=n)
    if not candles:
        return
    emas = ema_of(list(map(lambda c: c[field], reversed(candles))))

    return emas[-1]


def get_sma(ticker: str, day_of_action: date, n: int, field='c'):
    candles = get_last_n_candles(day_of_action, ticker, n=n)
    if not candles:
        return
    sma = current_sma_of(list(map(lambda c: c[field], candles)))

    return sma


def get_atr(ticker: str, day_of_action: date, n: int):
    candles = get_last_n_candles(day_of_action, ticker, n=n)
    if not candles:
        return
    atrs = atr_of(list(reversed(candles)))

    return atrs[0]


def get_ticker_changes(day_of_action: date, interesting_ticker: str):
    ticker_day_of_action, ticker_day_before = get_last_2_candles(
        day_of_action, interesting_ticker)

    return {
        "close_to_close_percent_change": (ticker_day_of_action['c'] - ticker_day_before['c']) / ticker_day_before['c'],
        "close_to_open_percent_change": (ticker_day_of_action['c'] - ticker_day_of_action['o']) / ticker_day_of_action['o']
    }


def get_spy_changes(day_of_action: date):
    return get_ticker_changes(day_of_action, interesting_ticker="SPY")
