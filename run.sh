#!/bin/bash

# in crontab:
# 1 * * * * cd /Users/jamesfulford/scanners && ./run.sh

. paper.env ; python3 run.py
