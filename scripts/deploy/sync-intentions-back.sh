#!/bin/bash

# TODO: allow different directories based on target server/environment
rsync -razv solomon:~/intentions/ ~/intentions 
