#!/bin/bash -e
current_dir=`pwd`
ENV_NAME=`basename $current_dir`
PARENT_DIR=`dirname $current_dir`

APP_DIR=$current_dir
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
    CONTAINER_NAME=${CONTAINER_NAME:-"$ENV_NAME-$action"}
    docker kill $CONTAINER_NAME >/dev/null 2>/dev/null || true
    docker rm $CONTAINER_NAME >/dev/null 2>/dev/null || true
    docker run -i \
        --env-file "$env_file" \
        --env "GIT_COMMIT=$GIT_COMMIT" \
        --env "DRY_RUN=$DRY_RUN" \
        --env "DEBUG=$DEBUG" \
        -v "$DATA_DIR":/data \
        -v "$APP_DIR":/app \
        $daemon \
        --name "$CONTAINER_NAME" \
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
    current_dir=`pwd`
    exit_code=0
    cd $DATA_DIR/inputs/td-token && ./refresh-tokens.sh || exit_code=1
    if [[ $exit_code -eq 1 ]]; then
        echo "ERROR failed to refresh tokens on first try, trying again with log output enabled..."
        ./refresh-tokens.sh || fail_script "Failed to refresh tokens"
    fi
    cd $current_dir
    return $exit_code
}

function refresh_tokens_if_needed() {
    if [[ `cat $env_file` == *"BROKER=td"* ]]; then
        echo "Refreshing tokens..."
        refresh_tokens || fail_script "Failed to refresh tokens"
        return
    fi
    echo "(no need to refresh tokens)"
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
        ./run.sh prepare-ticker-details-cache --end today --start end-0d
        # TODO: read this from LOOKUP_PERIOD of scanner
        ./run.sh prepare-grouped-aggs-cache --start end-1d --end today
        ;;

    "meemaw")
        run_python -c 'import src.log;from src.strat.meemaw.live import main; main()'
        ;;

    "clear-account")
        run_python -c 'import src.log;from src.strat.meemaw.clear_account import main; main()'
        ;;

    # Strategy: daily bracketing on NRGU
    "bracketing")
        run_python -c 'import src.log; from src.strat.bracketing.bracketing import main; main()'
        ;;

    # Strategy: Minion (NRGU 1m)
    "minion")
        run_python -c 'import src.log; from src.strat.minion.live import main; main()'
        ;;
    
    # Supernovas
    "supernovas")
        refresh_tokens_if_needed
        echo "Entering..."
        ALGO_NAME="supernovas" run_python -c "import src.log; from src.strat.scan_and_buy_market.enter import main; main()" "supernovas"
        echo
        echo "Setting up exit..."
        run_python -c "import src.log; from src.strat.scan_and_buy_market.egress import main; main()" 1.1 0.9
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
        run_python -c "import src.log; from src.reporting.dump_orders import main; main()" $1
        echo "(return code was $?)"
        ;;

    #
    # Backtesting Operations
    #
    "prepare-csvs")
        echo "UNIMPLEMENTED! prepare-csvs"
        exit 1
        # TODO: implement way to convert chronicles into CSVs we care about (aggregate by day? period shown?)
        # for script in $(ls $APP_DIR/src/scan/*.py | grep -v __init__); do
        #     module=`basename $script .py`
        #     echo "# running $module"
        #     run_python -c "import src.log; from src.scan.$module import prepare_csv; prepare_csv()"
        #     echo
        # done
        ;;
    
    "cache-migrate-v1-to-v2")
        run_python -c "import src.log; from src.caching.migrate import main; main()"
        ;;
    
    "create-chronicle")
        run_python -c "import src.log; from src.backtest.chronicle.create import main; main()" "$@"
        ;;

    "prepare-grouped-aggs-cache")
        run_python -c 'import src.log;from src.download.build_grouped_aggs_cache import main; main()' $@
        ;;
    
    "prepare-ticker-details-cache")
        run_python -c 'import src.log;from src.download.build_ticker_details_cache import main; main()' $@
        ;;

    "collector-nightly")
        ./run.sh prepare-grouped-aggs-cache --end today --start end-2y --clear # polygon free tier limits data to 2 years back
        ./run.sh prepare-ticker-details-cache --end today --start end-2y # match grouped-aggs cache

        # TODO: check at 9:00am, cancel this job if it's still running
        ./run.sh create-chronicle supernovas
        
        # TODO: restrict chronicle to only after 2022-01-15, not able to get short interest data before that
        # TODO: sync short interest cache to server
        # TODO: figure out float lookup caching and sync fundamentals cache to server
        # ./run.sh create-chronicle meemaw
        ;;

    "collector-morningly")
        ./run.sh prepare-ticker-details-cache --end today --start end-0d
        ;;
    
    "collector-sessionly")
        ./run.sh record-chronicle meemaw,supernovas,winners
        ;;
    
    #
    #
    #
    "record-chronicle")
        run_python -c "import src.log; from src.backtest.chronicle.record import main; main()" $1
        ;;

    #
    # Client Operations (across environments/accounts)
    #
    "sync-data")
        # ./scripts/deploy/sync-collector-data-back.sh collector

        for e in paper prod cash1 margin rothira; do
            echo
            echo Syncing $e...
            until ./scripts/deploy/sync-data-back.sh $e; do
                echo "rsync failed, retrying in 30 seconds..."
                sleep 30
            done
        done
        ;;

    "analyze-performance")
        run_python -c "import src.log; from src.reporting.performance import main; main()" "$@"
        ;;

    "build-drive-outputs")
        echo "Getting data (including trade intentions, cache, and orders csvs) from server..."
        ./run.sh sync-data

        # echo
        # echo "Building backtesting csvs..."
        # ./run.sh prepare-csvs

        echo
        echo "Analyzing performance..."
        ./run.sh analyze-performance --algoname meemaw --environments paper
        ./run.sh analyze-performance --algoname minion --environments margin
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
        for e in prod cash1 margin rothira; do
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
    
    "account-remote")
        SERVER_NAME=${SERVER_NAME:-"solomon"}

        function account() {
            local e=$1
            ssh $SERVER_NAME "cd ~/$e && ./run.sh account"
            return $?
        }

        for e in paper prod cash1 margin rothira; do
            echo
            echo "$e"
            account $e || (echo "(trying again in 30s)" && sleep 30 && account $e) || echo "ERROR with $e"
        done
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
