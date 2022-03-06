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

ENV_NAME=paper dev_source_env
ENV_NAME=cash1 dev_source_env
ENV_FILE=cash1.env ./run.sh refresh-tokens

nodemon -e py -x "DRY_RUN=1 python3 -c 'import src.log; from src.broker.generic import main; main()'"
