#!/bin/bash

environment=${1:-"paper"}
server="solomon"


mkdir -p ~/biggest-losers-data/remote-environments/$environment/
rsync -razv $server:~/$environment-data/ ~/biggest-losers-data/remote-environments/$environment/
