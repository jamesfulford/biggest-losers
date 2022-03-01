#!/bin/bash

environment=${1:-"paper"}
SERVER_NAME=${SERVER_NAME:-"solomon"}


function fail_script {
  echo "Failed to deploy to $environment"
  exit 1
}
rsync -razv ~/biggest-losers/ $SERVER_NAME:~/$environment
ssh $SERVER_NAME "cd ~/$environment && ./scripts/setup.sh" || fail_script

git tag -d $environment
git tag $environment
