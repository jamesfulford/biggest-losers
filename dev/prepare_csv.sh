#!/bin/bash

mkdir -p $HOME/data
mkdir -p $HOME/intentions
nodemon -e py -x ". paper.env ; python3 prepare_csv.py"