#!/bin/bash




export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/var/opt/OpenJDK-1.8.0.92-bin/bin:/var/opt/OpenJDK-1.8.0.92-bin/jre/bin
export HOME=/root

SCRIPTNAME='/opt/automation/lib/disk-warm-up.rb'
PIDFILE=/var/run/disk-warm-up.rb.pid

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
METHOD=$1

if ps aux | grep $SCRIPTNAME | grep -q ruby; then
  echo "Script already running! Exiting"
  exit 255
else
  echo "Getting VMs IP Address..."
  ruby $DIR/lib/get-vm-ip.rb
  echo "Done"
  source $DIR/conf/credential.conf
  echo "Starting warming up disks..."
  nohup ruby $DIR/lib/disk-warm-up.rb $METHOD > $DIR/logs/vmdk-warmup.log 2>&1 &
  echo "Warming up process started"

  RESULT=`ps -ef | grep ${SCRIPTNAME} | grep ruby`
  PID=`echo ${RESULT}|awk '{ print $2 }'`
  echo $PID > $PIDFILE
fi
