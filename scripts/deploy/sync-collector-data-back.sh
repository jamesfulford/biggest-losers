#!/bin/bash -e

function sync_local_data_dir_subdir_safe() {
  local subdir=$1

  until rsync -razv ~/biggest-losers-data/$subdir/ solomon:~/collector-data/$subdir;
  do
    echo "rsync failed, retrying in 30 seconds..."
    sleep 30
  done
}

function sync_data_dir_subdir() {
  local subdir=$1

  until rsync --delete -razv solomon:~/collector-data/$subdir/ ~/biggest-losers-data/$subdir;
  do
    echo "rsync failed, retrying in 30 seconds..."
    sleep 30
  done
}

function safe_sync_data_dir_subdir() {
  # No --delete, so we keep current dir

  local subdir=$1

  until rsync -razv solomon:~/collector-data/$subdir/ ~/biggest-losers-data/$subdir;
  do
    echo "rsync failed, retrying in 30 seconds..."
    sleep 30
  done
}

sync_local_data_dir_subdir_safe cache
sync_data_dir_subdir cache
safe_sync_data_dir_subdir chronicles
