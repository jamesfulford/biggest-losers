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
    current_dir=`pwd`
    exit_code=0
    cd $DATA_DIR/inputs/td-token && ./refresh-tokens.sh > /dev/null 2>&1 || exit_code=1 
    cd $current_dir
    return $exit_code
}

function refresh_tokens_if_needed() {
    if [ "$BROKER" == "td" ]; then
        echo "Refreshing tokens..."
        refresh_tokens || fail_script "Failed to refresh tokens"
    fi
}

action="$1"

case $action in
    "buy")
        refresh_tokens_if_needed
        case $BROKER in
            "alpaca")
                $python_exec biggest-losers-alpaca.py "buy" "$2"
                echo "(return code was $?)"
                ;;
            "td")
                $python_exec biggest-losers-td.py "buy" "$2"
                echo "(return code was $?)"
                ;;
            *)
                echo "Unknown broker: '$BROKER', exiting"
                exit 1
                ;;
        esac
        ;;
    "sell")
        refresh_tokens_if_needed
        case $BROKER in
            "alpaca")
                $python_exec biggest-losers-alpaca.py "sell" "$2"
                echo "(return code was $?)"
                ;;
            "td")
                $python_exec biggest-losers-td.py "sell" "$2"
                echo "(return code was $?)"
                ;;
            *)
                echo "Unknown broker: '$BROKER', exiting"
                exit 1
                ;;
        esac
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
    *)
        echo "unknown action $action"
        exit 1
        ;;
esac
