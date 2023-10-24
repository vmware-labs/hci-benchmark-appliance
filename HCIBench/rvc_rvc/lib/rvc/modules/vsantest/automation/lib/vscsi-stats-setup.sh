#!/bin/sh

# The local path to mount the RAM disk
STATS_DIR=$1

# The RAM disk capacity in MB
STATS_RAM_DISK_CAPACITY_MB=16384

mkdir -p ${STATS_DIR}
localcli system visorfs ramdisk add -m 256 -M ${STATS_RAM_DISK_CAPACITY_MB} -n vscsi-stats -t ${STATS_DIR} -p 0700
err=$?
if [ $err -ne 0 ]; then
        echo Failed to create RAM disk under ${STATS_DIR} >&2
        exit $err
fi