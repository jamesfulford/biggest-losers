#!/bin/bash

echo "Getting data (including trade intentions and orders csvs) from server..."
./scripts/deploy/sync-data-back.sh paper
./scripts/deploy/sync-data-back.sh prod
./scripts/deploy/sync-data-back.sh td-cash

echo "Preparing theoretical backtest numbers..."
./run.sh biggest-losers-csv

echo "Starting analysis..."
nodemon -e py -x "python3 analyze.py"
