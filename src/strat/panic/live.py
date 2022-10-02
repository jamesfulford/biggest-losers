import pprint
from src.entries.sizing import size_buy
import datetime
import logging

from src.outputs.intention import log_intentions
from src.strat.pdt import assert_pdt

from src import trading_day
from src.wait import wait_until
# TODO: polygon does not allow candles to be fetched on same day on free tier
from src.data.finnhub.finnhub import get_1m_candles, get_d_candles
from src.broker.generic import get_positions, get_account, buy_symbol_market, sell_symbol_market


ALGO_NAME = "panic"


def entry(data_symbol: str, entry_symbol: str):
    percentage_threshold = -0.01
    time_before_open_for_premarket_measurement = datetime.timedelta(minutes=5)

    now = trading_day.now()
    market_open = trading_day.get_market_open_on_day(now.date())
    if not market_open:
        logging.error(f"No market open found for {now}, exiting.")
        return
    if market_open < now:
        logging.warning(
            f"Running at wrong time, {now=} is after {market_open=}")

    premarket_time_of_interest = market_open - \
        time_before_open_for_premarket_measurement
    wait_until(premarket_time_of_interest)

    candles_1m = get_1m_candles(data_symbol, now.date(), now.date())
    if not candles_1m:
        logging.error(f"No 1m candles found on {now.date()}, exiting.")
        return

    last_1m_candle_before_open = [
        c for c in candles_1m if c['datetime'] < market_open][-1]
    premarket_price_unadjusted = last_1m_candle_before_open['close']
    premarket_candle_close_time = last_1m_candle_before_open['datetime'] + datetime.timedelta(
        minutes=1)
    logging.debug(
        f"{premarket_price_unadjusted=} {premarket_candle_close_time=}")

    account = get_account()
    cash = float(account["cash"])
    logging.info(f"{cash=}")

    wait_until(market_open + datetime.timedelta(seconds=2))
    query_start, query_end = trading_day.n_trading_days_ago(
        now.date(), 4), now.date()
    candles_d = get_d_candles(data_symbol, query_start, query_end)
    if not candles_d:
        logging.error(
            f"Could not find {data_symbol} daily candles between {query_start} - {query_end}, exiting")
        return

    today_candle_d = candles_d[-1]
    if today_candle_d['date'] != now.date():
        logging.warning(
            f"Last candle's date ({today_candle_d['date']}) is not today's date ({now.date()}), assuming no trading, exiting.")
        return
    today_open_adjusted = today_candle_d['open']

    prior_candle_d = candles_d[-2]
    prior_close_adjusted = prior_candle_d['close']
    logging.debug(
        f"{premarket_price_unadjusted=} {today_open_adjusted=} {prior_close_adjusted=}")

    # adjustment: frame of reference is today
    # - yesterday's close is adjusted to today
    # - today's premarket price is already in correct frame of reference
    # - today's open price is already in correct frame of reference
    percent_changed_premarket = (
        premarket_price_unadjusted / prior_close_adjusted) - 1
    percent_changed_open = (today_open_adjusted / prior_close_adjusted) - 1
    logging.debug(
        f"{percent_changed_premarket=:.1%} {percent_changed_open=:.1%}")

    #
    # ENTRY CRITERIA
    #
    criteria_passes_premarket = percent_changed_premarket < percentage_threshold
    criteria_passes_open = percent_changed_open < percentage_threshold
    # if not criteria_passes_premarket:
    #     logging.info(
    #         f"premarket percent change ({percent_changed_premarket:.1%}) was not under {percentage_threshold:.1%}, doing nothing.")
    #     return

    logging.info("Criteria met, sending orders and logging intentions.")

    #
    # ENTRY AND SIZING
    #
    # Do sizing and collect data on inverse symbol
    entry_symbol_candles_d = get_d_candles(
        entry_symbol, now.date(), now.date())
    if not entry_symbol_candles_d:
        logging.warning(
            f"Could not find daily candles for {entry_symbol} on {now.date()}, exiting.")
        return
    last_entry_symbol_candle_d = entry_symbol_candles_d[-1]
    entry_symbol_price = last_entry_symbol_candle_d['close']

    # Logging intentions
    cash_to_use = 100
    if cash_to_use > cash:
        # new_cash_to_use = cash * 0.9 # leave some room for fees, slipping, etc.
        # logging.warning(f"Insufficient cash on hand to enter, using less (Had {cash}, wanted {cash_to_use}, will instead use {new_cash_to_use})")
        # cash_to_use = new_cash_to_use

        logging.warning(
            f"Insufficient cash on hand to enter, skipping. (Had {cash}, wanted {cash_to_use})")
        return
    target_quantity = cash_to_use // entry_symbol_price
    intention = {
        "datetime": trading_day.now(),
        "symbol": entry_symbol,
        "price": entry_symbol_price,
        "side": "buy",
        "quantity": target_quantity,
    }
    metadata = {
        # account state
        "account": account,
        # symbol current values
        "last_d_candle": candles_d[-1],
        "last_entry_symbol_candle_d": last_entry_symbol_candle_d,
        # prices
        "premarket_price_unadjusted": premarket_price_unadjusted,
        "today_open_adjusted": today_open_adjusted,
        "prior_close_adjusted": prior_close_adjusted,
        # percent changes
        "percent_changed_premarket": percent_changed_premarket,
        "percent_changed_open": percent_changed_open,
        # decision criteria
        "percentage_threshold": percentage_threshold,
        # decision outcome(s)
        "criteria_passes_premarket": criteria_passes_premarket,
        "criteria_passes_open": criteria_passes_open,
        # sizing inputs
        "cash_to_use": cash_to_use,
        "target_quantity": target_quantity,
    }
    log_intentions(ALGO_NAME, [intention], metadata)
    buy_symbol_market(entry_symbol, target_quantity)


def main():
    # assert_pdt()

    entry("SPY", "SH")


if __name__ == "__main__":
    main()
