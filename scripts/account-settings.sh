#!/bin/bash

suspend_trade="$1"
if [[ "false" == "$suspend_trade" ]]; then
    suspend_trade="false"
else    
    suspend_trade="true"
fi

echo "suspend_trade: $suspend_trade"

curl --silent --fail -X PATCH \
    -H "APCA-API-KEY-ID: $APCA_API_KEY_ID" \
    -H "APCA-API-SECRET-KEY: $APCA_API_SECRET_KEY" \
    ${ALPACA_URL}/v2/account/configurations \
    -d "{
        \"dtbp_check\": \"both\",
        \"max_margin_multiplier\": 4,
        \"fractional_trading\": true,
        \"no_shorting\": true,
        \"suspend_trade\": $suspend_trade,
        \"trade_confirm_email\": \"all\"
    }" | python3 -m json.tool
