#!/bin/bash

. paper.env && nodemon -e py -x "python3 -c 'import src.log; from src.get_candles import main; main()'"
