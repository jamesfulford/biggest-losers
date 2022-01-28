from time import sleep

from src.trading_day import now


def wait_until(t, verbose=False):
    while True:
        market_time = now()

        if market_time >= t:
            if verbose:
                print(f"{t} is here")
            break

        seconds_remaining = (
            t - market_time
        ).seconds + 1  # so no crazy loop in last few milliseconds

        if verbose:
            print(f"{market_time} is before {t}, waiting {seconds_remaining} seconds")

        sleep(min(seconds_remaining, 60))
