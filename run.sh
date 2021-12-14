#!/bin/bash


current_dir=`pwd`
ENV_NAME=`basename $current_dir`
PARENT_DIR=`dirname $current_dir`

APP_DIR=$current_dir
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

source $DATA_DIR/inputs/.env

# select correct python command (python3.9 manually installed on server, python3 on my laptop)
python_exec=python3
py3_version=`$python_exec --version`
if [[ $py3_version != *"3.9"* ]]; then
    python_exec=python3.9
fi


action="$1"

case $action in
    "buy")
        $python_exec run.py "buy" "$2"
        echo "(return code was $?)"
        ;;
    "sell")
        $python_exec run.py "sell" "$2"
        echo "(return code was $?)"
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
