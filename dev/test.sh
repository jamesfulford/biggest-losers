#!/bin/bash

ENV_NAME=${ENV_NAME:-"paper"}

function dev_source_env() {
    ENV_NAME=${ENV_NAME:-"paper"}
    if [[ ! -f $ENV_NAME.env ]]; then
        echo "Could not find $ENV_NAME.env, exiting"
        exit 1
    fi
    cat $ENV_NAME.env | sed "s/..*/export &/" > active.dev.env
    source active.dev.env
}

dev_source_env
if [ "$BROKER" == "td" ]; then
    ENV_FILE=$ENV_NAME.env ./run.sh refresh-tokens
fi

nodemon -e py -x "DRY_RUN=1 coverage run -m pytest src && coverage lcov -o coverage.xml"


