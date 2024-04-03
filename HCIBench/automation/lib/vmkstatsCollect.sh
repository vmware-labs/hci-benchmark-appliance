#!/bin/sh

dumper=/usr/lib/vmware/vmkstats/bin/vmkstatsdumper
interval=60
dumpDir=/tmp/hcibench_vmkstats_dumpDir

#vmkstats:
#config remove: Remove any existing configuration and free up the reserved counter.
vsish -e set /perf/vmkstats/command/config remove
#configures the default event at startup
vsish -e set /perf/vmkstats/command/config default
#stop
vsish -e set /perf/vmkstats/command/stop
#reset
vsish -e set /perf/vmkstats/command/reset
#clear previous shit
rm -rf $dumpDir
#create dump dir
mkdir $dumpDir
#get into dir
cd $dumpDir
#generate vsanworlds.txt
ps -c | grep -i "vsan\|LSOMHelper\|LLOGHelper\|PLOGHelperQueue\|LFHelper\|LSOM2-\|splinter\|Cmpl-vmhba\|NVMeComplWorld\|ZDOM\|RDT\|VMNIC" > vsanworlds.txt
ps -c > worlds.txt
#start
vsish -e set /perf/vmkstats/command/start
#wait 1min
sleep $interval
#stop
vsish -e set /perf/vmkstats/command/stop
#dump
$dumper -d
$dumper -a -o $dumpDir
