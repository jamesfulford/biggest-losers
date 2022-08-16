
import datetime
import logging
import pprint
import typing
import numpy as np
import pandas as pd

from requests import HTTPError
import ta
from src.broker.generic import get_account, get_positions
from src.strat.pdt import assert_pdt
from src.trading_day import now, previous_trading_day
from src.wait import get_next_minute_mark, wait_until
from src.data.finnhub import finnhub
from src.data.finnhub.aggregate_candles import filter_candles_during_market_hours


ALGO_NAME = "apples"

FOR_ENTRY_AND_EXIT = "FOR_ENTRY_AND_EXIT"
FOR_ENTRY = "FOR_ENTRY"
NO = "NO"


def should_continue():
    return now().time() < datetime.time(15, 59)


def loop(params: dict):
    while should_continue():
        try:
            execute_phases(params)
        except HTTPError as e:
            logging.exception(
                f"HTTP {e.response.status_code} {e.response.text}")
        except Exception as e:
            logging.exception(f"Unexpected Exception")


def should_close(next_minute, current_position, account, params):
    next_minute_time = next_minute.time()
    if next_minute_time > datetime.time(9, 32) and next_minute_time < datetime.time(11, 30):
        return False
    if next_minute_time > datetime.time(14, 30) and next_minute_time < datetime.time(15, 58):
        return False

    if next_minute_time < datetime.time(9, 30) or next_minute_time >= datetime.time(16, 0):
        logging.warning("Outside of session, can't close position")
        return False
    return True


def should_open_no_candles(next_minute, account, params):
    return True
    next_minute_time = next_minute.time()
    if next_minute_time > datetime.time(9, 32) and next_minute_time < datetime.time(11, 30):
        return True
    if next_minute_time > datetime.time(14, 30) and next_minute_time < datetime.time(15, 58):
        return True

    if next_minute_time < datetime.time(9, 30) or next_minute_time >= datetime.time(16, 0):
        logging.info("Outside of session, can't open position")
        return False
    return True


def execute_phases(params: dict):
    symbol = "AAPL"

    next_minute = get_next_minute_mark(now())

    # Preparation Phase
    # wait_until(next_minute - datetime.timedelta(seconds=5))

    positions = get_positions()
    account = get_account()

    # TODO: do in options
    current_position = next(
        filter(lambda p: p['symbol'] == symbol, positions), None)
    logging.info(current_position)
    logging.info(account)

    # Execution Phase
    # need to always wait for the next minute, otherwise we can get a very fast loop
    wait_until(next_minute)

    if current_position:  # exit criteria (pre-candle fetch)
        # optimization: if we're already in a position, don't need to fetch candles
        if should_close(next_minute, current_position, account, params):
            logging.info(f"Closing position {current_position}")
            # TODO: actually close position
            return
        else:
            logging.info(f"Position {current_position} remains open")
            return

    if not current_position:  # entry criteria (pre-candle fetch)
        if not should_open_no_candles(next_minute, account, params):
            # early skipping
            logging.info(f"Not time to open position")
            return

    fetch_start, fetch_end = previous_trading_day(
        previous_trading_day(next_minute.date())), next_minute.date()
    candles = finnhub.get_1m_candles(symbol, fetch_start, fetch_end)
    if not candles:
        logging.warning(
            "No candles found in ({start}, {end}) for {symbol}, will not process entry criteria")
        return

    logging.info("evaluating entry criteria")


class Params(typing.TypedDict):
    use_cci: str
    cci_period: int
    cci_factor: float
    cci_upper: float
    cci_lower: float

    use_macd: str
    macd_settings: typing.Tuple[int, int, int]

    use_emacross: str
    emas: typing.Iterable[int]
    emas_cross_criteria_any_instead_of_all: bool
    emas_any_on_cross_instead_of_while_rightly_ordered: bool

    use_psar: str
    psar_af: float
    psar_afmax: float
    psar_period: int

    use_psar_lookback: str
    psar_lookback_period: int

    use_mfi: str
    mfi_period: int
    mfi_upper: float
    mfi_lower: float

    # Must be strong
    use_adx: str
    adx_period: int
    adx_min_strength: float

    # Must be getting stronger
    use_adx_slope: str
    adx_slope_smoothing_period: int

    # Indicate direction (better than PSAR, ideally)
    use_di: str
    di_period: int

    use_long_ema: str
    long_ema_period: int

    start_of_morning: datetime.time
    end_of_morning: datetime.time
    start_of_afternoon: datetime.time
    end_of_day: datetime.time

    verbose: bool


def compute_technicals(candles, params: Params):
    highs = pd.Series(list(map(lambda c: float(c["high"]), candles)))
    lows = pd.Series(list(map(lambda c: float(c["low"]), candles)))
    closes = pd.Series(list(map(lambda c: float(c["close"]), candles)))
    volumes = pd.Series(list(map(lambda c: float(c["volume"]), candles)))

    technicals = {}

    # https://technical-analysis-library-in-python.readthedocs.io/en/latest/ta.html

    #
    # CCI
    #
    ccis = ta.trend.CCIIndicator(
        highs, lows, closes, window=params['cci_period'], constant=params['cci_factor']).cci()
    technicals['cci'] = {
        "value": ccis.values[-1],
        "long_signal": ccis.values[-1] > params['cci_upper'],
        "short_signal": ccis.values[-1] < params['cci_lower'],
    }

    #
    # MACD
    #
    fast_period, slow_period, signal_period = params['macd_settings']
    macds = ta.trend.MACD(closes, window_slow=slow_period,
                          window_fast=fast_period, window_sign=signal_period)
    technicals['macd'] = {
        "value": macds.macd().values[-1],
        "signal": macds.macd_signal().values[-1],
        "long_signal": macds.macd().values[-1] > macds.macd_signal().values[-1],
        "short_signal": macds.macd().values[-1] < macds.macd_signal().values[-1],
    }

    #
    # EMAs
    #
    # TODO: implement on-cross signaling
    assert not params['emas_any_on_cross_instead_of_while_rightly_ordered'], "not implemented"

    technicals['ema'] = {}

    ema_signals = [ta.trend.EMAIndicator(
        closes, window=ema_period).ema_indicator() for ema_period in params['emas']]
    ema_values = [ema.values[-1] for ema in ema_signals]

    for ema_period, ema_value in zip(params['emas'], ema_values):
        technicals['ema'][f"value_{ema_period}"] = ema_value

    # "while rightly ordered"
    rightly_ordered_upside = True
    rightly_ordered_downside = True
    for i in range(len(ema_values) - 1):
        fast, slow = ema_values[i], ema_values[i + 1]
        if fast > slow:
            rightly_ordered_downside = False
        elif fast < slow:
            rightly_ordered_upside = False

    state = "up" if rightly_ordered_upside else "down" if rightly_ordered_downside else "mixed"
    long_signal = state in (
        ["up", "mixed"] if params['emas_cross_criteria_any_instead_of_all'] else ["up"])
    short_signal = state in (
        ["down", "mixed"] if params['emas_cross_criteria_any_instead_of_all'] else ["down"])

    technicals['ema']['state'] = state
    technicals['ema']['long_signal'] = long_signal
    technicals['ema']['short_signal'] = short_signal

    #
    # PSAR
    #
    psars = ta.trend.PSARIndicator(
        highs, lows, closes, step=params['psar_af'], max_step=params['psar_afmax']).psar()
    technicals['psar'] = {
        "value": psars.values[-1],
        "close": closes.values[-1],
        "long_signal": psars.values[-1] < closes.values[-1],
        "short_signal": psars.values[-1] > closes.values[-1],
    }

    #
    # PSAR lookback
    #
    technicals['psar_lookback'] = {
        "value": psars.values[-params['psar_lookback_period']],
        "close": closes.values[-params['psar_lookback_period']],
        # must have been facing the wrong way N candles ago
        "long_signal": psars.values[-params['psar_lookback_period']] > closes.values[-params['psar_lookback_period']],
        "short_signal": psars.values[-params['psar_lookback_period']] < closes.values[-params['psar_lookback_period']],
    }

    #
    # MFI
    #
    mfis = ta.volume.MFIIndicator(
        highs, lows, closes, volumes, window=params['mfi_period']).money_flow_index()
    technicals['mfi'] = {
        "value": mfis.values[-1],
        "long_signal": mfis.values[-1] > params['mfi_upper'],
        "short_signal": mfis.values[-1] < params['mfi_lower'],
    }

    #
    # ADX
    #
    # suppressing warning about invalid operation (outputs and inputs look healthy)
    # https://numpy.org/doc/stable/reference/generated/numpy.seterr.html
    # says is usually caused by gettings nulls/nans/empty lists, none of which I have observed.
    """
    /usr/local/lib/python3.9/site-packages/ta/trend.py:769: RuntimeWarning: invalid value encountered in double_scalars
      dip[idx] = 100 * (self._dip[idx] / value)
    /usr/local/lib/python3.9/site-packages/ta/trend.py:774: RuntimeWarning: invalid value encountered in double_scalars
      din[idx] = 100 * (self._din[idx] / value)
    """
    np.seterr(invalid="ignore")
    adx_result = ta.trend.ADXIndicator(
        highs, lows, closes, window=params['adx_period'], fillna=True)
    np.seterr(invalid="warn")
    adxs = adx_result.adx()
    technicals['adx'] = {
        "value": adxs.values[-1],
        "long_signal": adxs.values[-1] > params['adx_min_strength'],
        "short_signal": adxs.values[-1] > params['adx_min_strength'],
    }

    #
    # ADX Slope
    #
    assert params["adx_slope_smoothing_period"] >= 1
    prior_value = adxs.values[-params["adx_slope_smoothing_period"] - 1]
    adx_slope = (adxs.values[-1] - prior_value) / \
        params["adx_slope_smoothing_period"]
    technicals["adx_slope"] = {
        "slope": adx_slope,
        "prior_value": prior_value,
        "long_signal": adx_slope > 0,
        "short_signal": adx_slope < 0,
    }

    #
    # DI
    #
    np.seterr(invalid="ignore")
    adx_result = ta.trend.ADXIndicator(
        highs, lows, closes, window=params['di_period'], fillna=True)
    np.seterr(invalid="warn")
    dipluses = adx_result.adx_pos()
    diminuses = adx_result.adx_neg()
    technicals['di'] = {
        "DI+": dipluses.values[-1],
        "DI-": diminuses.values[-1],
        "long_signal": dipluses.values[-1] > diminuses.values[-1],
        "short_signal": dipluses.values[-1] < diminuses.values[-1],
    }

    #
    # Long EMA
    #
    long_emas = ta.trend.EMAIndicator(
        closes, window=params['long_ema_period']).ema_indicator()
    technicals['long_ema'] = {
        "value": long_emas.values[-1],
        "long_signal": closes.values[-1] > long_emas.values[-1],
        "short_signal": closes.values[-1] < long_emas.values[-1],
    }

    #
    # Time of day
    #
    current_time = candles[-1]['datetime'].time()
    sessions = {
        "morning": (params['start_of_morning'], params['end_of_morning']),
        "afternoon": (params['start_of_afternoon'], params['end_of_day']),
    }
    session_status = {name: current_time >= start and current_time <=
                      end for name, (start, end) in sessions.items()}

    active_session = next(
        (name for name, is_active in session_status.items() if is_active), None)

    technicals['time_of_day'] = {
        "time": current_time,
        "active_session": active_session,
        "long_signal": active_session is not None,
        "short_signal": active_session is not None,
    }

    return technicals


def main():
    symbol = "AAPL"

    next_minute = get_next_minute_mark(now())

    fetch_start, fetch_end = previous_trading_day(
        previous_trading_day(next_minute.date())), next_minute.date()
    print(fetch_start, fetch_end)
    candles = finnhub.get_1m_candles(symbol, fetch_start, fetch_end)
    if not candles:
        return
    candles = filter_candles_during_market_hours(candles)

    params: Params = {'use_cci': 'FOR_ENTRY', 'cci_period': 20, 'cci_factor': 0.015, 'cci_upper': -1000, 'cci_lower': -100, 'use_macd': 'FOR_ENTRY', 'macd_settings': (12, 26, 9), 'use_emacross': 'FOR_ENTRY', 'emas': (9, 20, 50, 200), 'emas_cross_criteria_any_instead_of_all': True, 'emas_any_on_cross_instead_of_while_rightly_ordered': False, 'use_psar': 'NO', 'psar_af': 0.021, 'psar_afmax': 0.2, 'psar_period': 2, 'use_psar_lookback': 'NO', 'psar_lookback_period': 3,
                      'use_mfi': 'NO', 'mfi_period': 14, 'mfi_upper': 80, 'mfi_lower': 20, 'use_adx': 'FOR_ENTRY', 'adx_period': 14, 'adx_min_strength': 20, 'use_adx_slope': 'NO', 'adx_slope_smoothing_period': 5, 'use_di': 'FOR_ENTRY', 'di_period': 9, 'use_long_ema': 'NO', 'long_ema_period': 200, 'start_of_morning': datetime.time(9, 32), 'end_of_morning': datetime.time(11, 30), 'start_of_afternoon': datetime.time(14, 30), 'end_of_day': datetime.time(15, 57), 'verbose': True}

    pprint.pprint(compute_technicals(candles, params))

    return
    assert_pdt()

    logging.info(f"Starting live algo")
    loop(params)


if __name__ == "__main__":
    main()
