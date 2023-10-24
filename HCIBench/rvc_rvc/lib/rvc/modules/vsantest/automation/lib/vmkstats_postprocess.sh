#!/bin/bash

ODIR=$1
JARFILE=$2
JAVA=$3

if [[ -z "$JARFILE" ]]; then
   JARFILE="/build/trees/vmcore-main/bora/support/tools/java/vmcallstackview.jar"
fi

if [[ -z "$JAVA" ]]; then
   JAVA="java"
fi

BIN="$JAVA -jar $JARFILE --text -tag k"

# Caller, callee
cd $ODIR
$BIN -caller > caller.txt
$BIN -callee > callee.txt
$BIN -callee --maxdepth 1 > callee1.txt

#Affinity-based processing
if [[ -e "$ODIR/affinity.log" ]]; then
   CMD="$BIN --rootAt VSANServerMainLoop --caller"

   CONTEXTS="plog lsomllog owner client compserver"
   for CTX in $CONTEXTS; do
      cpuids=
      for cpu in `egrep -i "_$CTX" affinity.log | cut -d" " -f6`; do
         if [[ -z "$cpuids" ]]; then
            cpuids=$cpu
         else
            cpuids="$cpu,$cpuids"
         fi
      done
      if [[ ! -z "$cpuids" ]]; then
         $CMD --cpu "$cpuids" > $ODIR/$CTX.txt
      fi
   done
fi

## World-based processing
if [[ ! -e "$ODIR/vsanworlds.txt" ]]; then
   cd -
   exit 0
fi

CMD="$BIN --rootAt VSANServerMainLoop --caller"

CONTEXTS="plog lsomllog owner client compserver"
for CTX in $CONTEXTS; do
   wids=
   for wid in `egrep -i "VSAN_.*$CTX" vsanworlds.txt | cut -d" " -f1`; do
      if [[ -z "$wids" ]]; then
         wids=$wid
      else
         wids="$wid,$wids"
      fi
   done
   if [[ ! -z "$wids" ]]; then
      $CMD --world $wids > $CTX.txt
   fi
done
cd -
