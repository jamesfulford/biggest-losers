#!/bin/bash

./scripts/deploy/sync-intentions-back.sh
nodemon -e py -x ". .env ; python3 analyze.py"
