#!/bin/bash

function alpaca () {
    local verb="$1"
    local url_path="$2"

    echo "$verb $url_path"
    shift 2

    curl --silent -X $verb \
        -H "APCA-API-KEY-ID: $APCA_API_KEY_ID" \
        -H "APCA-API-SECRET-KEY: $APCA_API_SECRET_KEY" \
        ${ALPACA_URL}${url_path} \
        "$@" | python3 -m json.tool
    echo
}


alpaca GET /v1/account
alpaca GET /v1/positions
alpaca GET /v1/orders

alpaca DELETE /v2/orders
alpaca DELETE /v2/positions

alpaca GET /v1/account
alpaca GET /v1/positions
alpaca GET /v1/orders
