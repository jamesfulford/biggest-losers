#!/bin/bash -e
current_dir=`pwd`
ENV_NAME=`basename $current_dir`
PARENT_DIR=`dirname $current_dir`

APP_DIR=$current_dir
# TODO: work out pathing for local development and multiple data dirs (remote-environments folder)
DATA_DIR=$PARENT_DIR/$ENV_NAME-data

log_path=$DATA_DIR/logs/run.log

env_file=${ENV_FILE:-"$DATA_DIR/inputs/.env"}
source $env_file

# select correct python command (python3.9 manually installed on server, python3 on my laptop)
python_exec=python3
py3_version=`$python_exec --version`
if [[ $py3_version != *"3.9"* ]]; then
    python_exec=python3.9
fi

# 
# Execute action
#

function fail_script() {
    echo "ERROR $1"
    exit 1
}

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

export GIT_COMMIT=`git rev-parse --short HEAD`

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
        $python_exec biggest_losers_stocks.py "buy" "$2"
        ;;
    "biggest-loser-stocks-sell")
        refresh_tokens_if_needed
        $python_exec biggest_losers_stocks.py "sell" "$2"
        ;;

    # Strategy: biggest loser warrants
    "biggest-loser-warrants-buy")
        refresh_tokens_if_needed
        $python_exec biggest_losers_warrants.py "buy" "$2"
        ;;
    "biggest-loser-warrants-sell")
        refresh_tokens_if_needed
        $python_exec biggest_losers_stocks.py "sell" "$2"
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
        $python_exec dump-orders.py
        echo "(return code was $?)"
        ;;

    #
    # Backtesting Operations
    #
    "prepare-csvs")
        $python_exec prepare_csv_losers.py
        $python_exec prepare_csv_winners.py
        $python_exec prepare_csv_supernovas.py
        ;;

    "prepare-cache")
        echo TODO pass start and end
        exit 1
        # $python_exec prepare_cache.py --start "$2" --end "$3"
        ;;

    #
    # Client Operations (across environments/accounts)
    #
    "sync-data")
        ./scripts/deploy/sync-data-back.sh paper
        ./scripts/deploy/sync-data-back.sh prod
        ./scripts/deploy/sync-data-back.sh td-cash
        ./scripts/deploy/sync-data-back.sh intrac1

        echo TODO get csvs back from server
        ;;

    "analyze-performance")
        $python_exec performance.py
        ;;

    "build-drive-outputs")
        echo "Getting data (including trade intentions and orders csvs) from server..."
        ./run.sh sync-data
        echo "Analyzing performance..."
        ./run.sh analyze-performance
        ;;



    # Catchall
    *)
        echo "unknown action $action"
        exit 1
        ;;
esac
