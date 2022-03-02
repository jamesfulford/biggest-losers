#!/bin/bash -e
current_dir=`pwd`
ENV_NAME=`basename $current_dir`
PARENT_DIR=`dirname $current_dir`

APP_DIR=$current_dir
# TODO: work out pathing for local development and multiple data dirs (remote-environments folder)
DATA_DIR=$PARENT_DIR/$ENV_NAME-data

log_path=$DATA_DIR/logs/run.log

export GIT_COMMIT=`git rev-parse --short HEAD`

env_file=${ENV_FILE:-"$DATA_DIR/inputs/.env"}

# run python inside container
# 1. same local and on server
# 2. easier to install ta-lib (royal pain due to C being awful)
function run () {
    local daemon=""
    if [ "$RUN_DAEMON" != "" ]; then
        daemon="-d"
    fi
    docker run -i --rm \
        --env-file "$env_file" \
        --env "GIT_COMMIT=$GIT_COMMIT" \
        --env "DRY_RUN=$DRY_RUN" \
        --env "DEBUG=$DEBUG" \
        -v "$DATA_DIR":/data \
        -v "$APP_DIR":/app \
        $daemon \
        --name $ENV_NAME-$RANDOM \
        "talib-py-runner" "$@"
}

function run_python () {
    run python3 -u "$@"
}

function fail_script() {
    echo "ERROR $1"
    exit 1
}


#
# TD tokens handling
#
function refresh_tokens() {
    container_name=$1
    current_dir=`pwd`
    exit_code=0
    cd $DATA_DIR/inputs/td-token && ./refresh-tokens.sh "$container_name" || exit_code=1
    if [[ $exit_code -eq 1 ]]; then
        echo "ERROR failed to refresh tokens on first try, trying again with log output enabled..."
        ./refresh-tokens.sh "$container_name" || fail_script "Failed to refresh tokens"
    fi
    cd $current_dir
    return $exit_code
}

function refresh_tokens_if_needed() {
    if [ ! -f $DATA_DIR/inputs/td-token/output/token.json ]; then
        echo "(no need to refresh tokens)"
        return
    fi
    echo "Refreshing tokens..."
    refresh_tokens "td-token-$RANDOM" || fail_script "Failed to refresh tokens"
}

action="$1"
shift 1

case $action in
    "account")
        run_python -c 'import src.log;import json;from src.broker.generic import get_account;print(json.dumps(get_account(), indent=2, sort_keys=True))'
        ;;

    #
    # Server actions
    #
    # TODO: simulate our own crontab by calling our own task manager script every minute from true crontab
    # - puts rules in file in codebase, stop editing crontab on server
    # - can fix timezone issue
    "refresh-tokens")
        refresh_tokens
        ;;

    # Strategy: biggest loser stocks
    "biggest-loser-stocks-buy")
        refresh_tokens_if_needed
        run_python -c 'import src.log; from src.strat.losers.stocks import main; main()' "buy"
        ;;
    "biggest-loser-stocks-sell")
        refresh_tokens_if_needed
        run_python -c 'import src.log; from src.strat.losers.stocks import main; main()' "sell"
        ;;

    # Strategy: biggest loser warrants
    "biggest-loser-warrants-buy")
        refresh_tokens_if_needed
        run_python -c 'import src.log; from src.strat.losers.warrants import main; main()' "buy"
        ;;
    "biggest-loser-warrants-sell")
        refresh_tokens_if_needed
        run_python -c 'import src.log; from src.strat.losers.warrants import main; main()' "sell"
        ;;

    # Strategy: meemaw
    "meemaw-prepare")
        run_python prepare_cache.py --start end-3d --end today
        ;;

    "meemaw")
        run_python -c 'import src.log;from src.strat.meemaw.live import main; main()' meemaw
        ;;

    "clear-account")
        run_python -c 'import src.log;from src.strat.meemaw.clear_account import main; main()'
        ;;

    # Strategy: daily bracketing on NRGU
    "bracketing")
        # TODO: refresh TD tokens continuously when TD support added for bracketing
        run_python -c 'import src.log; from src.strat.bracketing.bracketing import main; main()'
        ;;

    # TODO: refresh TD tokens continuously
    # Strategy: Minion (NRGU 1m)
    "minion")
        run_python -c 'import src.log; from src.strat.minion.live import main; main()'
        ;;

    # Operations
    "rotate-logs")
        if [[ -f $log_path.$(date +%Y-%m-%d) ]]; then
            echo "# already found today's log file, won't rotate"
            exit 0
        fi
        echo "# rotating logs" >> $log_path
        cp -f $log_path $log_path.$(date +%Y-%m-%d)
        echo "# starting new log" > $log_path
        ;;

    # Performance
    "dump-orders")
        refresh_tokens_if_needed
        run_python -c "import src.log; import src.reporting.dump_orders"
        echo "(return code was $?)"
        ;;

    #
    # Backtesting Operations
    #
    "prepare-csvs")
        for script in $(ls $APP_DIR/src/scan/*.py | grep -v __init__); do
            module=`basename $script .py`
            echo "# running $module"
            run_python -c "import src.log; from src.scan.$module import prepare_csv; prepare_csv()"
            echo
        done
        ;;

    "prepare-cache")
        run_python prepare_cache.py --end today --start end-2y  # polygon free tier limits data to 2 years back
        ;;

    "collector-nightly")
        ./run.sh prepare-cache
        # preparing csvs costs lots of memory, so let's not do it on tiny droplet server
        ;;
    #
    # Client Operations (across environments/accounts)
    #
    "sync-data")
        ./scripts/deploy/sync-collector-data-back.sh collector

        for e in collector paper prod td-cash cash1 intrac1; do
            echo
            echo Syncing $e...
            until ./scripts/deploy/sync-data-back.sh $e; do
                echo "rsync failed, retrying in 30 seconds..."
                sleep 30
            done
        done
        ;;

    "analyze-performance")
        run_python performance.py
        ;;

    "build-drive-outputs")
        echo "Getting data (including trade intentions, cache, and orders csvs) from server..."
        ./run.sh sync-data

        echo
        echo "Building backtesting csvs..."
        ./run.sh prepare-csvs

        echo
        echo "Analyzing performance..."
        ./run.sh analyze-performance
        ;;
    
    "deploy")
        TARGET_ENV=${1}
        if [[ "$TARGET_ENV" == "" ]]; then
            echo "Usage: deploy <environment>"
            exit 1
        fi
        echo "Deploying $TARGET_ENV..."
        until ./scripts/deploy/send-to-server.sh $TARGET_ENV; do
            echo "rsync failed, retrying in 30 seconds..."
            sleep 30
        done
        ;;

    "test-deploy")
        echo "Testing deploy..."
        for e in paper; do
            ./run.sh deploy $e
        done
        ;;

    "prod-deploy")
        for e in prod cash1 margin collector intrac1; do
            ./run.sh deploy $e
        done
        ;;
    
    "td-login")
        sleep 3 && python -m webbrowser -n "https://localhost:8000" &
        cd $DATA_DIR/inputs/td-token && ./start-login.sh
        ;;
    
    "td-login-remote")
        TARGET_ENV=${1}
        if [[ "$TARGET_ENV" == "" ]]; then
            echo "Usage: td-login-remote <environment>"
            exit 1
        fi
        SERVER_NAME=${SERVER_NAME:-"solomon"}
        sleep 3 && python -m webbrowser -n "https://localhost:8000" &
        ssh -L 8000:127.0.0.1:8000 $SERVER_NAME "cd ~/$TARGET_ENV-data/inputs/td-token && ./start-login.sh"
        ;;

    "create-env-td")
        TARGET_ENV=${1}
        if [[ "$TARGET_ENV" == "" ]]; then
            echo "Usage: create-env-td <environment>"
            exit 1
        fi
        SERVER_NAME=${SERVER_NAME:-"solomon"}
        ./scripts/deploy/send-to-server.sh $TARGET_ENV || true

        if [[ ! -f $TARGET_ENV.env ]]; then
            echo "Creating $TARGET_ENV.env"

            echo "POLYGON_API_KEY=" > $TARGET_ENV.env
            echo "FINNHUB_API_KEY=" >> $TARGET_ENV.env
            echo "BROKER=td" >> $TARGET_ENV.env
            echo "TD_ACCOUNT_ID=" >> $TARGET_ENV.env
        fi
        vi "$TARGET_ENV.env"
        scp $TARGET_ENV.env $SERVER_NAME:~/$TARGET_ENV-data/inputs/.env
        ssh $SERVER_NAME "test -d ~/$TARGET_ENV-data/inputs/td-token || git clone https://github.com/jamesfulford/td-token.git ~/$TARGET_ENV-data/inputs/td-token"

        # copy certs
        ssh $SERVER_NAME "mkdir -p ~/$TARGET_ENV-data/inputs/td-token/cert"
        scp $DATA_DIR/inputs/td-token/cert/cert.crt $SERVER_NAME:~/$TARGET_ENV-data/inputs/td-token/cert/cert.crt
        scp $DATA_DIR/inputs/td-token/cert/key.key $SERVER_NAME:~/$TARGET_ENV-data/inputs/td-token/cert/key.key
        scp $DATA_DIR/inputs/td-token/.env $SERVER_NAME:~/$TARGET_ENV-data/inputs/td-token/.env

        # get tokens
        SERVER_NAME="$SERVER_NAME" ./run.sh td-login-remote "$TARGET_ENV"

        ./scripts/deploy/send-to-server.sh "$TARGET_ENV"
        ;;

    # Catchall
    *)
        echo "unknown action $action"
        exit 1
        ;;
esac
