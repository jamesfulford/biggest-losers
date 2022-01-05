#!/bin/bash -e

environment=${1:-"collector"}
server="solomon"

# this rsync does not delete existing files in local directory, only syncs over *-matched files on remote server
# NOTE: deletes on remote are not done locally, so need to totally clear local cache before running
rm -rf ~/biggest-losers-data/cache/grouped_aggs_*
rsync --delete -razv $server:~/$environment-data/cache/grouped_aggs_* ~/biggest-losers-data/cache

rsync --delete -razv $server:~/$environment-data/outputs/*.csv ~/biggest-losers-data/outputs
