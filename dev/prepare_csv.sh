#!/bin/bash

mkdir -p $HOME/data
mkdir -p $HOME/intentions
nodemon -e py -x ". .env ; python3 prepare_csv.py"