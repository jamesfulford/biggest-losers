#!/bin/bash

# dump orders into csv
. paper.env && python3 dump-orders.py

# get intentions from server
./scripts/deploy/sync-data-back.sh

# analyze
nodemon -e py -x ". paper.env ; python3 analyze.py"
