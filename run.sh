#!/bin/bash

# in crontab:
# */10 * * * 1-5 cd /Users/jamesfulford/scanners && ./run.sh >> /tmp/run.log 2>&1

. paper.env ; /usr/local/bin/python3 run.py

H=$(date +%H)
if (( 12 <= 10#$H && 10#$H < 13 )); then 
    echo midday, rotating logs
    if [[ -f /tmp/run.log.$(date +%Y-%m-%d) ]]; then
        echo "found log file, won't rotate"
        exit 0
    fi
    cp -f /tmp/run.log /tmp/run.log.$(date +%Y-%m-%d)
    echo starting new log
fi
