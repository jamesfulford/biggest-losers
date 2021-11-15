#!/bin/bash

# in crontab:
# */10 * * * 1-5 cd /Users/jamesfulford/scanners && ./run.sh >> /tmp/run.log 2>&1

. paper.env ; python3 run.py
