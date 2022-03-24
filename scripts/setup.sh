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
mkdir -p $DATA_DIR/cache/finnhub/candles
mkdir -p $DATA_DIR/cache/polygon/candles
mkdir -p $DATA_DIR/cache/polygon/ticker_details
mkdir -p $DATA_DIR/cache/polygon/grouped_aggs
mkdir -p $DATA_DIR/cache/yh_finance/v3_stats
mkdir -p $DATA_DIR/cache/td/fundamentals

mkdir -p $DATA_DIR/chronicles

# utility for handling error messages less verbosely in bash
function fail_script() {
    echo "ERROR $1"
    exit 1
}

#
# check creds exist
#
test -f $DATA_DIR/inputs/.env || fail_script "could not find $DATA_DIR/inputs/.env"
source $DATA_DIR/inputs/.env || fail_script "$DATA_DIR/inputs/.env must be sourceable"


#
# Build container (if already built, will hit cache)
#
# docker build -t "talib-py-runner" . || fail_script "Failed to build docker container"


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

#
# BROKER setup
#

case $BROKER in
    "none")
        echo "BROKER=none, skipping broker setup"
        assert_crontab_entry_exists "cd $APP_DIR && ./run.sh collector-nightly >> $DATA_DIR/logs/run.log 2>&1"
        assert_crontab_entry_exists "cd $APP_DIR && ./run.sh rotate-logs"
        exit 0
        ;;
    "alpaca")
        echo "using alpaca"
        ./scripts/alpaca-ops/account-settings.sh "false" || fail_script "failed to set up settings"
        ;;
    "td")
        echo "using td"
        current_dir=`pwd`
        test -f $DATA_DIR/inputs/td-token/output/token.json || fail_script "could not find $DATA_DIR/inputs/td-token/output/token.json, follow instructions here: https://github.com/jamesfulford/td-token"
        cd $DATA_DIR/inputs/td-token && ./refresh-tokens.sh || fail_script "failed to refresh tokens"
        cd $current_dir
        ;;
    *)
        fail_script "BROKER '$BROKER' is unexpected value"
        ;;
esac


#
# check crontab entries (don't suggest doing locally and on server for same broker creds, can get confusing)
#
# assert_crontab_entry_exists "cd $APP_DIR && ./run.sh biggest-loser-[a-z]*-sell >> $DATA_DIR/logs/run.log 2>&1"
# assert_crontab_entry_exists "cd $APP_DIR && ./run.sh biggest-loser-[a-z]*-buy >> $DATA_DIR/logs/run.log 2>&1"
# assert_crontab_entry_exists "cd $APP_DIR && ./run.sh dump-orders >> $DATA_DIR/logs/run.log 2>&1"
# assert_crontab_entry_exists "cd $APP_DIR && ./run.sh rotate-logs"

#
# assert that scripts still run, but don't execute any trades for this test
#
# DRY_RUN=1 ./run.sh biggest-loser-stocks-buy || fail_script "failed to run biggest-loser-stocks-buy"
# DRY_RUN=1 ./run.sh biggest-loser-stocks-sell || fail_script "failed to run biggest-loser-stocks-sell"

# DRY_RUN=1 ./run.sh biggest-loser-warrants-buy || fail_script "failed to run biggest-loser-warrants-buy"
# DRY_RUN=1 ./run.sh biggest-loser-warrants-sell || fail_script "failed to run biggest-loser-warrants-sell"

./run.sh dump-orders || fail_script "failed to run dump-orders"
