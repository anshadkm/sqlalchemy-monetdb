#!/usr/bin/bash

set -x
set -e

FARM=/tmp/monetdb

monetdbd stop ${FARM}
rm -rf ${FARM}

set +e
set +x
