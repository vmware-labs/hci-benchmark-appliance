#!/bin/bash

export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/var/opt/OpenJDK-1.8.0.92-bin/bin:/var/opt/OpenJDK-1.8.0.92-bin/jre/bin
export HOME=/root
 

SCRIPTNAME="/opt/automation/lib/start-testing.rb"
if ps aux | grep $SCRIPTNAME | grep -q ruby
then
  echo "Script already running! Exiting"
  exit 255
else
  echo "Finished"
  exit 255
fi

