#!/bin/bash

. td-cash.env && nodemon -e py -x "python3 -c 'from src.broker.td import main; main()'"