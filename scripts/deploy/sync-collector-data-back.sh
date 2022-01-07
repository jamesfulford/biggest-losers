#!/bin/bash -e

# this rsync does not delete existing files in local directory, only syncs over *-matched files on remote server
# NOTE: deletes on remote are not done locally, so removing old files locally here
rm -f ~/collector-data/cache/grouped_aggs_*
until rsync --delete -razv solomon:~/collector-data/cache/grouped_aggs_* ~/biggest-losers-data/cache;
do
  echo "rsync failed, retrying in 30 seconds..."
  sleep 30
done
