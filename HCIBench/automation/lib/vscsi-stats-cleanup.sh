#!/bin/sh

# The local path to mount the RAM disk
STATS_DIR=$1

localcli system visorfs ramdisk remove -t ${STATS_DIR}
err=$?
if [ $err -ne 0 ]; then
        echo Failed to remove RAM disk under ${STATS_DIR} >&2
        exit $err
fi
rm -rf ${STATS_DIR}