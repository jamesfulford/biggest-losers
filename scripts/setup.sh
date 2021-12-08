#!/bin/bash

function fail_script() {
    echo "ERROR $1"
    exit 1
}

which python3 || fail_script "could not find 'python3'"
which pip3 || fail_script "could not find 'pip3'"

pip3 install -r requirements.txt || fail_script "failed to install requirements.txt"

# TODO: account for time and timezones in crontab entries
crontab -l | grep -q "cd ~/biggest-losers && \./run\.sh buy >> /tmp/run\.log 2>&1" || fail_script "could not find buy cron job"
crontab -l | grep -q "cd ~/biggest-losers && \./run\.sh sell >> /tmp/run\.log 2>&1" || fail_script "could not find sell cron job"
test -f ~/biggest-losers/run.sh || fail_script "could not find run.sh referenced by crontab"

# paper
test -f .env || fail_script "could not find .env"
source .env || fail_script ".env must be sourceable"
./scripts/ops/account-settings.sh "false" || fail_script "failed to set up settings"
