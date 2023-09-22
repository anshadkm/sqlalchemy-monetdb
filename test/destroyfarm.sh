#!/usr/bin/bash

set -x
set -e

FARM=/tmp/farm

monetdbd stop ${FARM}
rm -rf ${FARM}

set +e
set +x
