#!/bin/bash -e


current_dir=`pwd`
ENV_NAME=`basename $current_dir`
PARENT_DIR=`dirname $current_dir`

APP_DIR=$current_dir
# TODO: work out pathing for local development and multiple data dirs (remote-environments folder)
DATA_DIR=$PARENT_DIR/$ENV_NAME-data

echo APP_DIR $APP_DIR
echo DATA_DIR $DATA_DIR

log_path=$DATA_DIR/logs/run.log


# if running live on my remote server,
# send output of this script to log file
if [ "$DRY_RUN" == "" ] && [ "`whoami`" == "root" ]; then
    function cleanup () {
        echo
        echo "### End of script at `date`"
        echo
        killall tail
    }
    trap 'cleanup' EXIT
    tail -f $log_path &  # send logs to current terminal, but cleanup tail afterwards
    exec >> $log_path 2>&1  # send logs to log file

    echo
    echo "### Start of script at `date`"
    echo "### $@"
    echo
fi

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
    # biggest loser stocks
    "biggest-loser-stocks-buy")
        refresh_tokens_if_needed
        $python_exec biggest_losers_stocks.py "buy" "$2"
        ;;
    "biggest-loser-stocks-sell")
        refresh_tokens_if_needed
        $python_exec biggest_losers_stocks.py "sell" "$2"
        ;;

    # biggest loser warrants
    "biggest-loser-warrants-buy")
        refresh_tokens_if_needed
        $python_exec biggest_losers_warrants.py "buy" "$2"
        ;;
    "biggest-loser-warrants-sell")
        refresh_tokens_if_needed
        $python_exec biggest_losers_stocks.py "sell" "$2"
        ;;

    "rotate-logs")
        if [[ -f $log_path.$(date +%Y-%m-%d) ]]; then
            echo "# already found today's log file, won't rotate"
            exit 0
        fi
        echo "# rotating logs"
        cp -f $log_path $log_path.$(date +%Y-%m-%d)
        echo "# starting new log"
        ;;
    "dump-orders")
        refresh_tokens_if_needed
        $python_exec dump-orders.py
        echo "(return code was $?)"
        ;;
    "biggest-losers-csv")
        $python_exec prepare_csv.py
        echo "(return code was $?)"
        ;;
    "build-drive-outputs")
        echo "Getting data (including trade intentions and orders csvs) from server..."
        ./scripts/deploy/sync-data-back.sh paper
        ./scripts/deploy/sync-data-back.sh prod
        ./scripts/deploy/sync-data-back.sh td-cash
        ./scripts/deploy/sync-data-back.sh intrac1
        echo "Preparing theoretical backtest numbers..."
        ./run.sh biggest-losers-csv
        echo "Starting analysis..."
        $python_exec analyze.py
        ;;
    *)
        echo "unknown action $action"
        exit 1
        ;;
esac
