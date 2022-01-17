from src.criteria import is_etf, is_right, is_stock, is_warrant, is_unit
from src.grouped_aggs import get_today_grouped_aggs, get_last_trading_day_grouped_aggs


def get_volume_movers(today, skip_cache=False):
    today_grouped_aggs = get_today_grouped_aggs(today, skip_cache=skip_cache)
    if not today_grouped_aggs:
        print(f'no data for {today}, cannot fetch')
        return None
    yesterday_grouped_aggs = get_last_trading_day_grouped_aggs(today)

    # skip if wasn't present yesterday
    tickers_also_present_yesterday = list(filter(
        lambda t: t['T'] in yesterday_grouped_aggs['tickermap'], today_grouped_aggs['results']))

    for ticker in tickers_also_present_yesterday:
        previous_day_ticker = yesterday_grouped_aggs['tickermap'][ticker['T']]

        ticker['percent_volume_change'] = (
            ticker['v'] - previous_day_ticker['v']) / (previous_day_ticker['v'] + 1)  # added 1 to fix a divide by 0 issue
        ticker['previous_day_ticker'] = previous_day_ticker

    movers = list(
        filter(lambda t: t['percent_volume_change'] > 0, tickers_also_present_yesterday))

    movers = list(
        filter(lambda t: is_stock(t["T"], today) or is_etf(t["T"], today) or is_warrant(
            t["T"], today) or is_right(t["T"], today) or is_unit(t["T"], today), movers)
    )

    movers = sorted(movers, key=lambda t: -t['percent_volume_change'])

    for mover in movers:
        mover['rank'] = movers.index(mover) + 1

    volume_movers = list(
        filter(lambda t: t['rank'] <= 10, movers)
    )

    return volume_movers
    # return list(map(lambda mover: {
    #     "day_of_action": today,
    #     "mover_day_of_action": mover,
    #     "mover_day_before": yesterday_grouped_aggs['tickermap'][mover['T']],
    # }, volume_movers))
