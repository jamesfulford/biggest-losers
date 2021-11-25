from grouped_aggs import get_today_grouped_aggs, get_last_trading_day_grouped_aggs


def get_biggest_losers(today, top_n=20):
    today_grouped_aggs = get_today_grouped_aggs(today)
    if not today_grouped_aggs:
        print(f'no data for {today}, cannot fetch biggest losers')
        return None
    yesterday_grouped_aggs = get_last_trading_day_grouped_aggs(today)

    #
    # go find biggest losers for the next day
    #

    # skip if wasn't present yesterday
    tickers_also_present_yesterday = list(filter(
        lambda t: t['T'] in yesterday_grouped_aggs['tickermap'], today_grouped_aggs['results']))

    for ticker in tickers_also_present_yesterday:
        previous_day_ticker = yesterday_grouped_aggs['tickermap'][ticker['T']]

        ticker['percent_change'] = (
            ticker['c'] - previous_day_ticker['c']) / previous_day_ticker['c']

    biggest_losers = sorted(tickers_also_present_yesterday,
                            key=lambda t: t['percent_change'])[:top_n]

    for loser in biggest_losers:
        loser['rank'] = biggest_losers.index(loser) + 1

    return biggest_losers
