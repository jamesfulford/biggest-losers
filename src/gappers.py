from src.grouped_aggs import get_today_grouped_aggs, get_last_trading_day_grouped_aggs


def get_gappers(today, skip_cache=False):
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

        ticker['gap'] = (
            ticker['o'] - previous_day_ticker['c']) / previous_day_ticker['c']
        ticker['previous_day_ticker'] = previous_day_ticker

    movers = list(
        filter(lambda t: t['gap'] > .20, tickers_also_present_yesterday))

    movers = sorted(movers, key=lambda t: -t['gap'])

    for mover in movers:
        mover['rank'] = movers.index(mover) + 1

    return list(map(lambda mover: {
        "day_of_action": today,
        "mover_day_of_action": mover,
        "mover_day_before": yesterday_grouped_aggs['tickermap'][mover['T']],
    }, movers))
