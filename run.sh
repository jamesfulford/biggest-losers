#!/bin/bash

# in crontab:
# To Buy:
# 45 15 * * * cd /Users/jamesfulford/scanners && ./run.sh >> /tmp/run.log 2>&1
# To Sell:
# 0 20 * * * cd /Users/jamesfulford/scanners && ./run.sh >> /tmp/run.log 2>&1

echo
echo "###"
echo "### starting new run in run.sh"
echo "###"
echo
date
echo

mkdir -p $HOME/data

. paper.env ; /usr/local/bin/python3 run.py "$1"
echo "(return code was $?)"

H=$(date +%H)
if (( 12 <= 10#$H && 10#$H < 13 )); then 
    if [[ -f /tmp/run.log.$(date +%Y-%m-%d) ]]; then
        echo "# already found today's log file, won't rotate"
        exit 0
    fi
    echo "# rotating logs"
    cp -f /tmp/run.log /tmp/run.log.$(date +%Y-%m-%d)
    echo "# starting new log"
fi
