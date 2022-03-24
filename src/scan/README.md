# Scanners

## Backtesting

We want to simulate invoking a scanner every minute of every day for long periods of time. The scan results are stored in a chronicle file, which contains a JSON line for each scanner result every minute, in chronological order.

1. Prescan
2. Fetch 1m candles for each possible scanner result
3. Build simulated daily candles each minute for each ticker
4. Pass simulated daily candles to scanner filter
5. Append scanner filter results to JSONL file

## Prescan

Suppose we wanted to backtest for 2 years (~500 days) worth of data. Assume we already have the daily candles for all 10,000+ tickers on all of those days, but not the 1m candles. There are >10k tickers and 390 minutes a trading day, so that works out to 195k scanner invocations, 1.95 billion simulated candles to process, and 5 million days of 1m candles (20 days to download from finnhub @ 60rpm and 30 days of 1m candles per request). That's an unreasonable amount of processing and data to download and cache.

To reduce the number of 1m candles we need to fetch (and thus reduce number of daily candles to simulate intraday), every scanner needs to provide a basic prescanner to narrow the 10k tickers down to the few that could possibly be interesting, usually a 300 at most. That's 150k days of 1m candles to fetch (41 hours to download @ 1d of 1m candles per request; not 30d because we don't know if it will show up again).

Examples:

-   if scanning for a candle over a certain value, look if the "high" on the daily candle goes over that value. If it never does, then it can be discarded without having to fetch and compute every minute.
-   if volume has not reached minimum value by end of day, it certainly will not reach that volume intraday!
-   if open does not meet criteria, it never will during the day

The prescanner can be a separate function, however keeping it in sync with the scanner's logic poses risks in case of bad maintenance. Several tricks can be employed:

-   invoke the scanner, but only the non-expensive steps (put quotad APIs behind a kwarg only passed from prescanner)
    -   may use `with_kwargs` to pass the kwarg
    -   can use calculations belonging to steps 1-3 in filter order below, even some parts of 4, especially if batched, limited in calls, and/or unquotaed. Use your judgement.
    -   avoid fetching 1m candles, since that is what we are trying to avoid. No `candle_getter` is provided to prescanner, use `build_prescanner_with_empty_candle_getter` to make it easier to invoke scanner
-   if checking if "c" is over some value, replace "c" with "h". See `with_high_bias_prescan_strategy`.
-   if checking if "c" is under some value, replace "c" with "l". See `with_low_bias_prescan_strategy`.
-   do not limit by top N.
-   no need to sort (no harm beyond wasted compute)

## Filter order

Make sure to order filtering steps by how costly they are to perform. This way less computation and API quota is used, both in backtesting and live.

### 1. OHLCV of that day's candle

While "n" (count of trades) and "vw" (VWAP) are present, they will not work properly in backtests. Do not rely on these.

### 2. Calculations based on ticker

The symbol ("T") can be looked up and filtered with `is_stock`, `is_etf`, and other security classifications. This requires building cache once for each day, then it makes a few (1-3) cache calls for each batch of tickers. Since this is O(1) for each scanner invocation, this is fairly cheap.

### 3. Past daily candles

Candles for last few days can be looked up. The number of cache calls is below n\*t, where n is number of days prior ("LOOKUP_PERIOD") to look up and t is number of tickers present at this stage. If a ticker does not have activity on a day, it will be filtered out. (IPOs)

TODO: find out if long-halted stocks are included

### 4. API lookups

-   batched, ratelimited APIs (look up many tickers at once)
    -   TD's get_fundamentals API
-   ratelimited APIs
    -   e.g. 60 requests per minute, but quota replenishes regularly
    -   1m candle APIs (use candle_getter passed to scanner!)
-   quotaed APIs
    -   e.g. 500 requests a month
    -   YH Finance API (from RapidAPI)

### Suggestion: limit length

If lots of API lookups are used, then consider sorting the tickers and only performing lookups until N criteria-matching tickers are found.

## Scanner requirements

-   `LOOKUP_PERIOD`

Should be the number of past daily candles needed in cache to invoke. For example, if a calculation refers to previous day's close, use `1`. (This way we skip day 1 of cached days since previous candle is not available)

-   `def scanner`

-   `def prescanner`
