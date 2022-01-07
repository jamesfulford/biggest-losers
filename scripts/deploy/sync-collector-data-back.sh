#!/bin/bash -e

environment=${1:-"collector"}
server="solomon"

# this rsync does not delete existing files in local directory, only syncs over *-matched files on remote server
rsync --delete -razv $server:~/$environment-data/cache/grouped_aggs_* ~/biggest-losers-data/cache
# NOTE: deletes on remote are not done locally, so removing old files locally here
find ~/biggest-losers-data/cache -name 'grouped_aggs_*' -mtime 1 -delete
