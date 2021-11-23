#!/bin/bash

mkdir -p $HOME/data
nodemon -e py -x ". paper.env ; python3 prepare_csv.py"