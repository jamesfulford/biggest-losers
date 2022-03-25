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

#
# crontab setup
#
ln -s -f $APP_DIR/schedules/$ENV_NAME.crontab /etc/cron.d/$ENV_NAME || fail_script "could not create crontab link"

#
# BROKER setup
#

case $BROKER in
    "none")
        echo "BROKER=none, skipping broker setup"
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
# assert that scripts still run, but don't execute any trades for this test
#
./run.sh account || fail_script "failed to access account"

./run.sh dump-orders || fail_script "failed to run dump-orders"
