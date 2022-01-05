#!/bin/bash -e

environment=${1:-"paper"}
server="solomon"


mkdir -p ~/biggest-losers-data/remote-environments/$environment/
rsync --delete -razv $server:~/$environment-data/ ~/biggest-losers-data/remote-environments/$environment/
