#!/bin/bash -e
current_dir=`pwd`
ENV_NAME=`basename $current_dir`
PARENT_DIR=`dirname $current_dir`

APP_DIR=$current_dir
# TODO: work out pathing for local development and multiple data dirs (remote-environments folder)
DATA_DIR=$PARENT_DIR/$ENV_NAME-data

log_path=$DATA_DIR/logs/run.log

export GIT_COMMIT=`git rev-parse --short HEAD`

env_file=${ENV_FILE:-"$DATA_DIR/inputs/.env"}

# .env files are currently valid bash scripts, using `export` and quotes to set secrets.
# we are switching to docker run --env-file, which does not want `export` and will use quotes literally.
# TODO: stop rewriting .env files once all `export ` are removed
sed "s/^export //" "$env_file" > "$env_file.tmp"
mv "$env_file.tmp" "$env_file"

sed "s/\"//g" "$env_file" > "$env_file.tmp"
mv "$env_file.tmp" "$env_file"

# run python inside container
# 1. same local and on server
# 2. easier to install ta-lib (royal pain due to C being awful)
function run () {
    test ! -z "$(docker images -q talib-py-runner)" || docker build -t talib-py-runner .
    docker run -i --rm \
        --env-file "$env_file" \
        --env "GIT_COMMIT=$GIT_COMMIT" \
        --env "DRY_RUN=$DRY_RUN" \
        -v "$DATA_DIR":/data \
        -v "$APP_DIR":/app \
        talib-py-runner "$@"
}

function run_python () {
    run python3 -u "$@"
}

function fail_script() {
    echo "ERROR $1"
    exit 1
}


#
# TD tokens handling
#
function refresh_tokens() {
    container_name=$1
    current_dir=`pwd`
    exit_code=0
    cd $DATA_DIR/inputs/td-token && ./refresh-tokens.sh "$container_name" > /dev/null 2>&1 || exit_code=1
    if [[ $exit_code -eq 1 ]]; then
        echo "ERROR failed to refresh tokens on first try, trying again with log output enabled..."
        ./refresh-tokens.sh "$container_name" || fail_script "Failed to refresh tokens"
    fi
    cd $current_dir
    return $exit_code
}

function refresh_tokens_if_needed() {
    if [ "$BROKER" == "td" ]; then
        echo "Refreshing tokens..."
        refresh_tokens "td-token-$TD_ACCOUNT_ID" || fail_script "Failed to refresh tokens"
    fi
}

action="$1"

case $action in
    #
    # Server actions
    #
    # TODO: simulate our own crontab by calling our own task manager script every minute from true crontab
    # - puts rules in file in codebase, stop editing crontab on server
    # - can fix timezone issue
    "refresh-tokens")
        refresh_tokens_if_needed
        ;;

    # Strategy: biggest loser stocks
    "biggest-loser-stocks-buy")
        refresh_tokens_if_needed
        run_python -c 'from src.strat.losers.stocks import main; main()' "buy"
        ;;
    "biggest-loser-stocks-sell")
        refresh_tokens_if_needed
        run_python -c 'from src.strat.losers.stocks import main; main()' "sell"
        ;;

    # Strategy: biggest loser warrants
    "biggest-loser-warrants-buy")
        refresh_tokens_if_needed
        run_python -c 'from src.strat.losers.warrants import main; main()' "buy"
        ;;
    "biggest-loser-warrants-sell")
        refresh_tokens_if_needed
        run_python -c 'from src.strat.losers.warrants import main; main()' "sell"
        ;;

    # Strategy: daily bracketing on NRGU
    "bracketing")
        # TODO: refresh TD tokens continuously when TD support added for bracketing
        run_python -c 'from src.strat.bracketing.bracketing import main; main()'
        ;;

    # TODO: refresh TD tokens continuously
    # Strategy: Minion (NRGU 1m)
    "minion")
        run_python -c 'from src.strat.nrgu.nrgu_live import main; main()'
        ;;

    # Operations
    "rotate-logs")
        if [[ -f $log_path.$(date +%Y-%m-%d) ]]; then
            echo "# already found today's log file, won't rotate"
            exit 0
        fi
        echo "# rotating logs" >> $log_path
        cp -f $log_path $log_path.$(date +%Y-%m-%d)
        echo "# starting new log" > $log_path
        ;;

    # Performance
    "dump-orders")
        refresh_tokens_if_needed
        run_python -c "import src.reporting.dump_orders"
        echo "(return code was $?)"
        ;;

    #
    # Backtesting Operations
    #
    "prepare-csvs")
        for script in $(ls $APP_DIR/src/scan/*.py | grep -v __init__); do
            module=`basename $script .py`
            echo "# running $module"
            run_python -c "from src.scan.$module import prepare_csv; prepare_csv()"
            echo
        done
        ;;

    "prepare-cache")
        run_python prepare_cache.py --end today --start end-2  # polygon free tier limits data to 2 years back
        ;;

    "collector-nightly")
        ./run.sh prepare-cache
        # preparing csvs costs lots of memory, so let's not do it on tiny droplet server
        ;;
    #
    # Client Operations (across environments/accounts)
    #
    "sync-data")
        ./scripts/deploy/sync-collector-data-back.sh collector

        for e in collector paper prod td-cash intrac1; do
            echo
            echo Syncing $e...
            until ./scripts/deploy/sync-data-back.sh $e; do
                echo "rsync failed, retrying in 30 seconds..."
                sleep 30
            done
        done
        ;;

    "analyze-performance")
        run_python performance.py
        ;;

    "build-drive-outputs")
        echo "Getting data (including trade intentions, cache, and orders csvs) from server..."
        ./run.sh sync-data

        echo
        echo "Building backtesting csvs..."
        ./run.sh prepare-csvs

        echo
        echo "Analyzing performance..."
        ./run.sh analyze-performance
        ;;

    "test-deploy")
        echo "Testing deploy..."
        ./scripts/deploy/send-to-server.sh paper
        ;;

    "prod-deploy")
        echo "Deploying..."
        for e in prod td-cash intrac1 collector; do
            ./scripts/deploy/send-to-server.sh $e || fail_script "Failed to deploy $e"
        done
        ;;

    # Catchall
    *)
        echo "unknown action $action"
        exit 1
        ;;
esac
