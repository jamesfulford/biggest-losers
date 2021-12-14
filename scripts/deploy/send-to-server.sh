#!/bin/bash

environment=${1:-"paper"}
server="solomon"


function fail_script {
  echo "Failed to deploy to $environment"
  exit 1
}
rsync -razv ~/biggest-losers/ $server:~/$environment
ssh $server "cd ~/$environment && ./scripts/setup.sh" || fail_script

git tag -d $environment
git tag $environment
