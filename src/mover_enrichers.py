from src.grouped_aggs import get_last_2_candles, get_last_n_candles, get_last_trading_day_grouped_aggs, get_today_grouped_aggs
from src.indicators import current_sma_of, ema_of, get_atr


def enrich_with_ema(mover, n, field='c'):
    ticker = mover["mover_day_of_action"]["T"]
    day_of_action = mover["day_of_action"]
    candles = get_last_n_candles(day_of_action, ticker, n=n)
    if not candles:
        return
    emas = ema_of(list(map(lambda c: c[field], reversed(candles))))

    mover[f"{n}ema"] = emas[-1]


def enrich_with_sma(mover, n, field='c'):
    ticker = mover["mover_day_of_action"]["T"]
    day_of_action = mover["day_of_action"]
    candles = get_last_n_candles(day_of_action, ticker, n=n)
    if not candles:
        return
    sma = current_sma_of(list(map(lambda c: c[field], candles)))

    mover[f"{n}sma"] = sma


def enrich_with_atr(mover, n):
    ticker = mover["mover_day_of_action"]["T"]
    day_of_action = mover["day_of_action"]
    candles = get_last_n_candles(day_of_action, ticker, n=n)
    if not candles:
        return
    atrs = get_atr(list(reversed(candles)))

    mover[f"{n}atr"] = atrs[0]


def enrich_with_adx(mover):
    ticker = mover["mover_day_of_action"]["T"]
    day_of_action = mover["day_of_action"]

    last_14_candles = get_last_n_candles(day_of_action, ticker, n=14)
    if not last_14_candles:
        return
    # TODO: complete implementation


def enrich_with_ticker_changes(mover, ticker):
    day_of_action = mover["day_of_action"]
    ticker_day_of_action, ticker_day_before = get_last_2_candles(
        day_of_action, ticker)

    mover[f"{ticker.lower()}_day_of_action_percent_change"] = (
        ticker_day_of_action['c'] - ticker_day_before['c']) / ticker_day_before['c']
    mover[f"{ticker.lower()}_day_of_action_intraday_percent_change"] = (
        ticker_day_of_action['c'] - ticker_day_of_action['o']) / ticker_day_of_action['o']


def enrich_with_spy_changes(mover):
    return enrich_with_ticker_changes(mover, ticker="SPY")
