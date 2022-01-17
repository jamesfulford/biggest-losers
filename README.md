# biggest-losers

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
8. `pip install -r requirements.txt` to install python dependencies.


TODO: what to do about `~/biggest-loser-data/outputs` syncing with Google Drive?

## Troubleshooting

### My TD Token is not refreshing / has expired

Follow instructions here to generate a new token using the server: https://github.com/jamesfulford/td-token

Then, scp the token to the remote server so it can be refreshed as needed.

```bash
scp output/token.json solomon:~/td-cash-data/inputs/td-token/output/token.json
```

(There might be issues with 2 different refreshers using the same tokens, it seems refreshing might cause expiration)
