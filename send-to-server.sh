#!/bin/bash

rsync -razv ~/biggest-losers/ solomon:~/biggest-losers/
ssh solomon "cd ~/biggest-losers && ./setup.sh"
