import argparse
from datetime import datetime, timedelta
from src.criteria import is_etf, is_right, is_stock, is_unit, is_warrant
from src.trading_day import generate_trading_days, now, today, today_or_previous_trading_day
import logging


def main():
    market_now = now()
    market_today = today(market_now)

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)

    args = parser.parse_args()

    if args.end == "today":
        end = market_today
    else:
        end = today_or_previous_trading_day(
            datetime.strptime(args.end, "%Y-%m-%d").date()
        )
    assert end <= market_today, "cannot query the future"

    start = today_or_previous_trading_day(market_today)
    if "end-" in args.start:
        start_str = args.start.replace("end-", "")
        if start_str.endswith("d"):
            days = int(start_str.replace("d", ""))
            start = today_or_previous_trading_day(
                end - timedelta(days=days))
        elif start_str.endswith('y'):
            years = int(start_str.replace("y", ""))
            start = today_or_previous_trading_day(
                end - timedelta(days=365 * years))
    else:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()

    assert start <= end, f"{start=} {end=}"

    print("start:", start)
    print("end:", end)
    print()

    logging.info("Started updating symbol details cache")
    for day in generate_trading_days(start, end):
        logging.info(f"Updating symbol details cache for {day}")
        is_stock("AAPL", day=day)
        is_etf("SPY", day=day)
        is_warrant("ADRW", day=day)
        is_right("ADRR", day=day)
        is_unit("ADRU", day=day)

    logging.info("Ending updating symbol details cache")


if __name__ == "__main__":
    main()
