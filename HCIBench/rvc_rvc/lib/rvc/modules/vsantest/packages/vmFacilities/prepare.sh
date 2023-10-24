#!/bin/bash

VERSION=$1
sh ~/tmp/reset-containers
systemctl stop docker
systemctl disable docker

echo $VERSION > /etc/hcibench_version
currentversion=`grep Welcome /etc/issue | awk '{print $5}'`
sed "s/$currentversion/$VERSION/g" -i /etc/issue*

cat /etc/issue

echo "------------------------"

cat /etc/issue.net

rm -rf /opt/automation/tmp/*
rm -rf /opt/automation/vdbench-param-files/*
rm -rf /opt/automation/conf/perf-conf.yaml
rm -rf /opt/automation/logs/*
rm -rf /opt/output/vdbench-source/*
rm -rf /opt/tmp/*
#rm -rf /opt/output/results/*

cp /root/glue.rb /root/tmp/ -f
tdnf clean all
yum clean all
rm -rf /var/log/journal/*
rm -rf /var/opt/apache-tomcat-8.5.68/logs/*
echo -n > /etc/machine-id
> /root/.rvc-history
> /root/.ssh/known_hosts
> /root/.rvc/known_hosts
cat /dev/zero > /root/temp.log
sync
sleep 3
rm /root/temp.log -f

cat /dev/zero > /opt/output/results/temp.log
sleep 3
rm -f /opt/output/results/temp.log

sh /root/tmp/shrinkDisks.sh
#sh /root/tmp/sysprep.sh -f
> /root/.bash_history
history -c
shutdown -h now
