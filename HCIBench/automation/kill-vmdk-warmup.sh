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

SCRIPTNAME='/opt/automation/lib/disk-warm-up.rb'
PIDFILE=/var/run/disk-warm-up.rb.pid
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

   echo "Process killed, rebooting client VMs..."
   ruby $DIR/lib/reboot-vms.rb 
   echo "Client VMs rebooted, getting IPs..."
   ruby $DIR/lib/get-vm-ip.rb 
   echo "Client VMs IP prepared"
   exit 255
else
   echo "No process is running"
   exit 255
fi
