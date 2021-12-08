#!/bin/bash

environment=${1:-"paper"}
server="solomon"

rsync -razv ~/biggest-losers/ $server:~/$environment
ssh $server "cd ~/$environment && ./scripts/setup.sh"

git tag -d $environment
git tag $environment
