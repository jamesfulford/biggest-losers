#!/bin/bash

current_dir=`pwd`
ENV_NAME=`basename $current_dir`
PARENT_DIR=`dirname $current_dir`

APP_DIR=$current_dir
DATA_DIR=$PARENT_DIR/$ENV_NAME-data

echo APP_DIR $APP_DIR
echo DATA_DIR $DATA_DIR

# make directories
mkdir -p $DATA_DIR/inputs
mkdir -p $DATA_DIR/outputs
mkdir -p $DATA_DIR/logs
mkdir -p $DATA_DIR/cache

# utility for handling error messages less verbosely in bash
function fail_script() {
    echo "ERROR $1"
    exit 1
}

#
# check things are installed
#
which python3 || fail_script "could not find 'python3'"
which pip3 || fail_script "could not find 'pip3'"

pip3 install -r requirements.txt || fail_script "failed to install requirements.txt"

#
# check creds exist and are valid, also configure account
#
test -f $DATA_DIR/inputs/.env || fail_script "could not find $DATA_DIR/inputs/.env"
source $DATA_DIR/inputs/.env || fail_script "$DATA_DIR/inputs/.env must be sourceable"
./scripts/ops/account-settings.sh "false" || fail_script "failed to set up settings"

#
# check crontab entries (don't suggest doing locally and on server for same broker creds, can get confusing)
#

# TODO: account for time and timezones in crontab entries
function assert_crontab_entry_exists() {
    local entry="$1"
    local grep_ready_entry=`echo "$entry" | python3 -c "import sys;print(sys.stdin.read().replace('.', '\\.'))"`  # replace . with \., for escaping in grep
    crontab -l | grep -q "$grep_ready_entry"
    exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        crontab -l
        fail_script "could not find crontab entry '$entry'. Run 'EDITOR=vi crontab -e' to add it."
    fi
}

assert_crontab_entry_exists "cd $APP_DIR && ./run.sh buy >> $DATA_DIR/logs/run.log 2>&1"
assert_crontab_entry_exists "cd $APP_DIR && ./run.sh sell >> $DATA_DIR/logs/run.log 2>&1"

DRY_RUN=1 ./run.sh buy || fail_script "failed to run buy"
DRY_RUN=1 ./run.sh sell || fail_script "failed to run sell"
