#!/usr/bin/bash

set -x
set +e

FARM="/tmp/monetdb"

# ps ax | grep monetdbd | grep -v grep | awk '{ print $1 }' | xargs kill -9

monetdbd stop ${FARM} || true
rm -rf ${FARM}
monetdbd create ${FARM} || true
monetdbd start ${FARM}

set -e
set +x
