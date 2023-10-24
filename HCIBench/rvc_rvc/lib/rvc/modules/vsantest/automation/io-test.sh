#!/bin/bash




export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/var/opt/OpenJDK-1.8.0.92-bin/bin:/var/opt/OpenJDK-1.8.0.92-bin/jre/bin
export HOME=/root
 
SCRIPTNAME='/opt/automation/lib/io-test.rb'
PIDFILE=/var/run/io-test.rb.pid

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

if ps aux | grep $SCRIPTNAME | grep -q ruby; then
  echo "Script already running! Exiting"
  exit 255
else
  echo "Starting HCIBench Testing"
  nohup ruby $DIR/lib/io-test.rb > $DIR/logs/io-testing.log 2>&1 &
  echo "HCIBench Testing Started"

  RESULT=`ps -ef | grep ${SCRIPTNAME} | grep ruby`
  PID=`echo ${RESULT}|awk '{ print $2 }'`
  echo $PID > $PIDFILE
fi
