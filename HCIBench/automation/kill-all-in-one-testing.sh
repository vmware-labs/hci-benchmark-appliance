#!/bin/bash

# Run script to stop telegraf process no matter what
`ruby /opt/automation/lib/stop_all_telegraf.rb`

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
echo $DIR
SCRIPTNAME="/opt/automation/lib/start-testing.rb"
PIDFILE=/var/run/start-testing.rb.pid
PID=

if ps aux | grep "${SCRIPTNAME}" | grep -q ruby; then
   #verify if the process is actually still running under this pid
   RESULT=`ps -ef | grep "${SCRIPTNAME}" | grep ruby`
   if [ -n "${RESULT}" ]; then
     PID=`echo ${RESULT}|awk '{ print $2 }'`
   else
     PID=`cat $PIDFILE`
   fi
   kill -9 $(list_descendants $PID)
   kill -9 $PID
   last_status=`tail -1 $DIR/logs/test-status.log`
   if echo $last_status | grep -q "Deployment Started"
   then
     echo "Process killed, deleting deployed client VMs..." | tee -a $DIR/logs/test-status.log
     ruby $DIR/lib/cleanup-vm.rb
     echo "Client VMs deleted, deployment aborted!" | tee -a $DIR/logs/test-status.log

   elif  echo $last_status | grep -q "Disk Preparation\|I/O Test Started\|Started Testing\|HERE TO MONITOR"
   then
     echo "Process killed, rebooting client VMs..." | tee -a $DIR/logs/test-status.log
     ruby $DIR/lib/reboot-vms.rb
     echo "Client VMs rebooted, getting IPs..." | tee -a $DIR/logs/test-status.log
     ruby $DIR/lib/get-vm-ip.rb
     echo "Client VMs IP prepared" | tee -a $DIR/logs/test-status.log
   fi
   # reset eth1 no matter what
   ifconfig -s eth1 0.0.0.0
   ifconfig eth1 down 
   ifconfig eth1 up
   exit 255
   
else
  echo "No process is running"
  exit 255
fi

