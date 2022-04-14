#!/bin/bash
rm -f ./view/code.tar
tar -cvf ./view/code.tar ./src/indicators/drawing_lines_logic.py
tar -rvf ./view/code.tar ./src/data/finnhub/aggregate_candles.py
tar -rvf ./view/code.tar ./src/data/types/candles.py
tar -rvf ./view/code.tar ./src/trading_day.py
