from src.grouped_aggs import get_today_grouped_aggs, get_last_trading_day_grouped_aggs


def get_supernovas(today, skip_cache=False, pct=2):
    today_grouped_aggs = get_today_grouped_aggs(today, skip_cache=skip_cache)
    if not today_grouped_aggs:
        print(f'no data for {today}, cannot fetch supernovas')
        return None
    yesterday_grouped_aggs = get_last_trading_day_grouped_aggs(today)

    #
    # go find supernovas for the next day
    #

    # skip if wasn't present yesterday
    tickers_also_present_yesterday = list(filter(
        lambda t: t['T'] in yesterday_grouped_aggs['tickermap'], today_grouped_aggs['results']))

    for ticker in tickers_also_present_yesterday:
        previous_day_ticker = yesterday_grouped_aggs['tickermap'][ticker['T']]

        ticker['percent_change_high'] = (
            ticker['h'] - previous_day_ticker['c']) / previous_day_ticker['c']
        ticker['previous_day_close'] = previous_day_ticker['c']
        ticker['previous_day_volume'] = previous_day_ticker['v']

    supernovas = list(
        filter(lambda t: t['percent_change_high'] > pct, tickers_also_present_yesterday))
    supernovas = sorted(supernovas,
                        key=lambda t: t['percent_change_high'])

    for nova in supernovas:
        nova['rank'] = supernovas.index(nova) + 1

    return list(map(lambda mover: {
        "day_of_action": today,
        "mover_day_of_action": mover,
        "mover_day_before": yesterday_grouped_aggs['tickermap'][mover['T']],
    }, supernovas))
