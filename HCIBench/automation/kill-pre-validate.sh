#!/bin/bash

export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/var/opt/OpenJDK-1.8.0.92-bin/bin:/var/opt/OpenJDK-1.8.0.92-bin/jre/bin
export HOME=/root

list_descendants ()
{
  local children=$(ps -o pid= --ppid "$1")

  for pid in $children
  do
    list_descendants "$pid"
  done

  echo "$children"
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
SCRIPTNAME="/opt/automation/lib/pre-validation.rb"
PIDFILE=/var/run/pre-validation.rb.pid
LOG_FILE="$DIR/logs/prevalidation/pre-validation.log"

if ps aux | grep "${SCRIPTNAME}" | grep -q ruby; then
  RESULT=$(ps -ef | grep "${SCRIPTNAME}" | grep ruby | grep -v grep)
  if [ -n "${RESULT}" ]; then
    PID=$(echo ${RESULT} | awk '{ print $2 }')
  else
    PID=$(cat $PIDFILE)
  fi
  kill -9 $(list_descendants $PID) 2>/dev/null
  kill -9 $PID 2>/dev/null

  echo "Pre-validation cancelled by user" >> $LOG_FILE

  # Clean up test VMs if they were being deployed
  ruby $DIR/lib/cleanup-tvm.rb 2>/dev/null

  # Reset eth1 in case static IP validation was in progress
  ifconfig -s eth1 0.0.0.0 2>/dev/null
  ifconfig eth1 down 2>/dev/null
  ifconfig eth1 up 2>/dev/null

  echo "Pre-validation process killed"
  exit 0
else
  echo "No pre-validation process is running"
  exit 0
fi
