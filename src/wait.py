import logging
from time import sleep

from src.trading_day import now


def wait_until(t):
    while True:
        market_time = now()

        if market_time >= t:
            logging.debug(f"{t} is here")
            break

        seconds_remaining = (
            t - market_time
        ).total_seconds() + .001  # +1ms so no crazy loop at end

        logging.debug(
            f"{market_time} is before {t}, waiting {seconds_remaining} seconds")

        sleep(min(seconds_remaining, 60))
