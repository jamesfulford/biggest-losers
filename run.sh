#!/bin/bash

# in crontab:
# To Buy:
# 45 15 * * * cd /Users/jamesfulford/scanners && ./run.sh buy >> /tmp/run.log 2>&1
# To Sell:
# 0 20 * * * cd /Users/jamesfulford/scanners && ./run.sh sell >> /tmp/run.log 2>&1

echo
echo "###"
echo "### starting new run in run.sh"
echo "###"
echo
date
echo

current_dir=`pwd`
ENV_NAME=`basename $current_dir`
PARENT_DIR=`dirname $current_dir`

APP_DIR=$current_dir
DATA_DIR=$PARENT_DIR/$ENV_NAME-data

echo APP_DIR $APP_DIR
echo DATA_DIR $DATA_DIR

log_path=$DATA_DIR/logs/run.log

source $DATA_DIR/inputs/.env

python_exec=python3
py3_version=`$python_exec --version`
if [[ $py3_version != *"3.9"* ]]; then
    python_exec=python3.9
fi

$python_exec run.py "$1" "$2"
echo "(return code was $?)"

H=$(date +%H)
if (( 12 <= 10#$H && 10#$H < 13 )); then 
    if [[ -f $log_path.$(date +%Y-%m-%d) ]]; then
        echo "# already found today's log file, won't rotate"
        exit 0
    fi
    echo "# rotating logs"
    cp -f $log_path $log_path.$(date +%Y-%m-%d)
    echo "# starting new log"
fi
