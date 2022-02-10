#!/bin/bash

./run.sh refresh-tokens
. cash1.env && . paper.env && nodemon -e py -x "DRY_RUN=1 python3 -c 'import src.log; from src.broker.generic import main; main()'"