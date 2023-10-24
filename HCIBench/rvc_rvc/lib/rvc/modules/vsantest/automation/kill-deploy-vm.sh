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

SCRIPTNAME='/opt/automation/lib/deploy-vms.rb'
PIDFILE=/var/run/deploy-vms.rb.pid
PID=

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

if ps aux | grep $SCRIPTNAME | grep -q ruby; then
   #verify if the process is actually still running under this pid
   RESULT=`ps -ef | grep ${SCRIPTNAME} | grep ruby`
   if [ -n "${RESULT}" ]; then
     PID=`echo ${RESULT}|awk '{ print $2 }'`
   else
     PID=`cat $PIDFILE`
   fi

   kill -9 $(list_descendants $PID)
   kill -9 $PID
   echo "Process killed, deleting deployed client VMs..."
   ruby $DIR/lib/cleanup-vm.rb
   echo "Client VMs deleted, deployment aborted!"

   exit 255
else
   echo "No process is running"
   exit 255
fi



