#!/bin/bash

current_dir=`pwd`
ENV_NAME=`basename $current_dir`
PARENT_DIR=`dirname $current_dir`
DATA_DIR=$PARENT_DIR/$ENV_NAME-data

. $DATA_DIR/inputs/.env && curl --silent -X POST \
        -H "APCA-API-KEY-ID: $APCA_API_KEY_ID" \
        -H "APCA-API-SECRET-KEY: $APCA_API_SECRET_KEY" \
        ${ALPACA_URL}/v2/orders \
        -d "{
            \"symbol\": \"ETHUSD\",
            \"notional\": \"1000\",
            \"side\": \"buy\",
            \"type\": \"market\",
            \"time_in_force\": \"gtc\"
        }" | python3 -m json.tool
