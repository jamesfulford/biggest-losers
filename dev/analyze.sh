#!/bin/bash

echo "Getting data (including trade intentions) from server..."
./scripts/deploy/sync-data-back.sh paper
./scripts/deploy/sync-data-back.sh prod

echo "Getting Filled orders from broker..."
echo TODO: make it hard to mix up paper and prod
. paper.env && python3 dump-orders.py paper
. prod.env && python3 dump-orders.py prod

echo "Preparing theoretical backtest numbers..."
. paper.env && python3 prepare_csv.py

echo "Starting analysis..."
nodemon -e py -x "python3 analyze.py"
