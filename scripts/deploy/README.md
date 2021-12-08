# Deployment Model

Each environment will have 2 folders each:

-   `~/{env}`: code
-   `~/{env}-data`:
    -   `./inputs` (config, secrets, etc.)
    -   `./outputs` (spreadsheets, for example)
    -   `./logs`
    -   `./cache` (API results. Can copy from cache to cache if we wish, but sharing cache can lead to bad things)

Additionally, each environment will have its own separate set of cron jobs.
