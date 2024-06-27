# biggest-losers

This repo contains my independent quantitative algo research and tools.

- "Biggest losers": in the 2020-2021 era, often, a small-cap stock that dropped a ton overnight was oversold and could be expected to come back up. Polygon.io has an API for fetching the daily candles for all exchange-listed stocks (non-OTC) for each day. This codebase downloaded all this data for the last year (would have done more if free tier allowed; re-downloaded daily because prices were adjusted) and computed the biggest losers and simulated buying and selling the next day. The results were promising, however I hit a ton of surprises: surprise delistings, data inaccuracies (buying at 3:50pm is not same price at close price... and MOC orders are executed at that price but had to be placed at 3:50 which means my logic may or may not have been accurate), ticker renaming, alpaca.markets (broker) not supporting purchasing warrants (switched to TD Ameritrade), overfitting in my backtesting, and avoiding fractional shares due to worse fills. I also learned it's important to look at performance over time, to see if the strategy continues to perform. Additionally, I learned how to monitor cron jobs using Cronitor.io and how to package Python scripts in Docker.
- "Meemaw": I was encouraged to look at trading NRGU, a 3x daily leveraged large-cap oil company ETN, with technical analysis mechanisms. I ran a script every 1 minute to check to see if I should buy or sell my position based on various indicators on the 1m chart (I liked RSI and ADX). The chart wasn't terribly thickly traded, so I investigated looking at alternative means of building my indicators. I learned how a trade is executed in detail, including limit orders versus market orders and the spread and level 1 versus level 2 versus level 3 data and how a price changes and what a market maker does and what is different for an ETF. I worked with backtrader for backtesting a ton. I started working with the quantstats package and learned how to evaluate whether a strategy (really, a series of trades) was good performance compared to its risk. I learned not only Sharpe ratio, but the Serenity ratio as a better measure for Modern Portfolio Theory. I was holding a lot of NRGU when the war in Ukraine began, and that singlehandedly explains why my algo trading venture was net positive (though was negative if you account for opportunity cost of continuing to work as a software engineer. Since those results are not reproducible, I'm not considering the compounding returns argument for staying in this area).
- Built a tool to evaluate switching a bunch of backtest trades into equivalent options trades in hopes of increasing leverage. I wouldn't recommend doing that.
- Built a tool to evaluate applying bracket orders to already-existing backtest trades. This seemed to make a difference, but I wasn't terribly pleased with results.
- Built tools to optimize sizing for a strategy given its past backtesting behavior and accounting for cash settling (T-2 for stocks and T-1 for options at TD Ameritrade; since then, SEC regulations have pushed most brokers to switch to T-1 cash settling for stocks, which simplifies this problem a *ton*).

## Managing Portainer

To make it run:

```bash
docker run -d -p 443:9443 --name portainer \
    --restart=always \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v portainer_data:/data \
    portainer/portainer-ce:2.11.1
```

To stop it (in case you want to upgrade):

```bash
docker stop portainer
docker rm portainer
```

## Set Up

1. Clone this repo to `~/biggest-losers`
2. Install Python 3.9 (or higher) (not lower, we need zoneinfo module for timezones). Running `python3 --version` should return `Python 3.9.x`
3. Install nodemon (install nodejs, then `npm install -g nodemon`; may need to use `sudo`)
4. Run the following:

```bash
mkdir -p ~/biggest-losers-data/cache
mkdir -p ~/biggest-losers-data/inputs
mkdir -p ~/biggest-losers-data/outputs
mkdir -p ~/biggest-losers-data/logs
```

5. Reference `.env.sample` and set up `paper.env` folder. Set `BROKER=none`. Create finnhub.io and polygon.io accounts, get API keys and paste them into `paper.env`.
6. Ask your best friend for a zip of their cache directory - it can take days to build that from scratch on Polygon Free tier (5 req / minute)
7. Add VS Code extensions for VS Code. Use pep8 autoformatter.
8. `pip3 install -r requirements.txt` to install python dependencies.

TODO: what to do about `~/biggest-loser-data/outputs` syncing with Google Drive?

## Troubleshooting

### My TD Token is not refreshing / has expired

Follow instructions here to generate a new token using the server: https://github.com/jamesfulford/td-token

Then, scp the token to the remote server so it can be refreshed as needed.

```bash
scp output/token.json solomon:~/td-cash-data/inputs/td-token/output/token.json
```

(There might be issues with 2 different refreshers using the same tokens, it seems refreshing might cause expiration)
