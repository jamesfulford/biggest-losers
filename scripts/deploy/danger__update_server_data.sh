#!/bin/bash

environment=${1:-"paper"}
server="solomon"

rsync -razv ~/biggest-losers-data/remote-environments/$environment/ $server:~/$environment-data/
