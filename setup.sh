#!/bin/bash

function fail_script() {
    echo "ERROR $1"
    echo exit 1
}

which python3 || fail_script "could not find 'python3'"
which pip3 || fail_script "could not find 'pip3'"

pip3 install -r requirements.txt || fail_script "failed to install requirements.txt"

crontab -l | grep -q "45 15 \* \* \* cd ~/biggest-losers && \./run\.sh >> /tmp/run\.log 2>&1" || fail_script "could not find buy cron job"
crontab -l | grep -q "0 20 \* \* \* cd ~/biggest-losers && \./run\.sh >> /tmp/run\.log 2>&1" || fail_script "could not find sell cron job"

# paper
test -f paper.env || fail_script "could not find paper.env"
source paper.env || fail_script "paper.env must be sourceable"
./account-settings.sh "false" || fail_script "failed to set up settings"
