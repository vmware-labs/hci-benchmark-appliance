#!/bin/bash
export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/var/opt/OpenJDK-1.8.0.92-bin/bin:/var/opt/OpenJDK-1.8.0.92-bin/jre/bin
export HOME=/root
 

DISK_NUM=
WORKING_SET=
THREADS_NUM=
BLOCK_SIZE=
READ_PERCENT=
RANDOM_PERCENT=
TEST_TIME=
WARMUP_TIME=
INTERVAL_TIME=
IO_RATE=
PREFIX=
COMP_RATIO=
DEDUP_RATIO=

# Function to display usage
usage()
{
 echo -e "Usage: $0 -n NUM_DataDisk -w WORKING_SET -t NUM_THREADS -b BLOCK_SIZE -r READ% -s RANDOM% -e Test_Time [-m Warmup_Time -i Interval_Second -c Compression_Ratio -d Deduplication_Ratio]"
 echo -e "\t-h\tDisplay this help information (required)"
 echo -e "\t-n\tNumber of Data Disk to be tested (required)"
 echo -e "\t-w\tWorking Set Percentage of Data Disk(0-100) (required)"
 echo -e "\t-b\tBlock Size (required)"
 echo -e "\t-r\tRead Percentage(0-100) (required)"
 echo -e "\t-s\tSeek(random) Percentage(0-100) (required)"
 echo -e "\t-e\tTesting Time(second) (required)"
 echo -e "\t-p\tProfile Prefix (optional)"
 echo -e "\t-t\tNumber of Threads per Data Disk (optional)"
 echo -e "\t-m\tWarmup Time(second) (optional)"
 echo -e "\t-i\tInterval(second) (optional)"
 echo -e "\t-o\tIORate (optional)"
 echo -e "\t-c\tCompression Ratio (optional)"
 echo -e "\t-d\tDeduplication Ratio (optional)" 
 echo -e "\nExample: $0 -n 5 -w 20 -t 2 -b 8k -r 35 -s 60 -e 600 -i 5 -o 15000 -c 2 -d 3"
}

verify_num()
{ 
  re='^[0-9]+([.][0-9]+)?$'
  if ! [[ $1 =~ $re ]] ; then
   echo "error: $1 Not a number" >&2; exit 1
  fi

}

chr()
{
  [ "$1" -lt 256 ] || return 1
  printf "\\$(printf '%03o' "$1")"
}

if [ $# -eq 0 ]
then
  echo "Error: $0 expects several arguments."
  usage
  exit 1
fi



while getopts ":h:n:w:t:b:r:s:e:m:i:p:o:c:d:" Option
do
  case $Option in
    h)
      usage
      exit 0
      ;;
    n)
      DISK_NUM=$OPTARG
      verify_num $DISK_NUM
      ;;
    w)
      WORKING_SET=$OPTARG
      verify_num $WORKING_SET
      ;;
    t)
      THREADS_NUM=$OPTARG
      verify_num $THREADS_NUM
      ;;
    b)
      BLOCK_SIZE=$OPTARG
      ;;
    r)
      READ_PERCENT=$OPTARG
      verify_num $READ_PERCENT
      ;;
    s)
      RANDOM_PERCENT=$OPTARG
      verify_num $RANDOM_PERCENT
      ;;
    e)
      TEST_TIME=$OPTARG
      verify_num $TEST_TIME
      ;;
    m)
      WARMUP_TIME=$OPTARG
      verify_num $WARMUP_TIME
      ;;
    i)
      INTERVAL_TIME=$OPTARG
      verify_num $INTERVAL_TIME
      ;;
    p)
      PREFIX="$OPTARG-"
      ;;
    o)
      IO_RATE=$OPTARG
      if [ $IO_RATE != "max" ]
      then
    	verify_num $IO_RATE
      fi
      ;;
    c)
      COMP_RATIO=$OPTARG
      verify_num $COMP_RATIO
      ;;
    d)
      DEDUP_RATIO=$OPTARG
      verify_num $DEDUP_RATIO
      ;;
    ?)
      usage
      exit
      ;;
  esac
done

if [[ ! -z $DISK_NUM&&$WORKING_SET&&$BLOCK_SIZE&&$READ_PERCENT&&$RANDOM_PERCENT&&$TEST_TIME  ]] 
then
echo good
else
  usage
  exit 1
fi


FILENAME="/opt/automation/vdbench-param-files/${PREFIX}vdb-${DISK_NUM}vmdk-${WORKING_SET}ws-${BLOCK_SIZE}-${READ_PERCENT}rdpct-${RANDOM_PERCENT}randompct-${THREADS_NUM}threads"

touch $FILENAME

echo "*Auto Generated VDBench Parameter File" > $FILENAME
echo "*$DISK_NUM raw disk, ${RANDOM_PERCENT}% random, ${READ_PERCENT}% read" >> $FILENAME
echo "*SD:    Storage Definition" >> $FILENAME
echo "*WD:    Workload Definition" >> $FILENAME
echo "*RD:    Run Definition" >> $FILENAME
echo "debug=86" >> $FILENAME
echo "data_errors=10000" >> $FILENAME

THREADS_VAR=",threads=2"
if [[ ! -z $THREADS_NUM ]]
then
  THREADS_VAR=",threads=$THREADS_NUM"
fi

IORATE_VAR=",iorate=max"
if [[ ! -z $IO_RATE ]]
then
 IORATE_VAR=",iorate=$IO_RATE"
fi

if [[ ! -z $COMP_RATIO ]]
then
  echo "compratio=$COMP_RATIO" >> $FILENAME
fi

if [[ ! -z $DEDUP_RATIO ]]
then
  echo "dedupratio=$DEDUP_RATIO" >> $FILENAME
  echo "dedupunit=4k" >> $FILENAME
fi

SD_VAR=

if [ $DISK_NUM -lt 27 ] #1~26 vmdks
then
  for i in `seq 1 $DISK_NUM`
  do
    echo "sd=sd${i},lun=/dev/sd`chr $( expr $i + 96 )`,openflags=o_direct,hitarea=0,range=(0,$WORKING_SET)$THREADS_VAR" >> $FILENAME
    SD_VAR=$SD_VAR"sd$i,"
  done
elif [ $DISK_NUM -gt 26 ] && [ $DISK_NUM -lt 53 ]  #27 vmdks to 52vmdk
then
  for i in `seq 1 26`
  do
    echo "sd=sd${i},lun=/dev/sd`chr $( expr $i + 96 )`,openflags=o_direct,hitarea=0,range=(0,$WORKING_SET)$THREADS_VAR" >> $FILENAME
    SD_VAR=$SD_VAR"sd$i,"
  done

  ADDITIONAL_DISK=$( expr $DISK_NUM - 26 )
  for i in `seq 1 $ADDITIONAL_DISK`
  do
    echo "sd=sd$( expr $i + 26 ),lun=/dev/sda`chr $( expr $i + 96 )`,openflags=o_direct,hitarea=0,range=(0,$WORKING_SET)$THREADS_VAR" >> $FILENAME
    SD_VAR=$SD_VAR"sd$( expr $i + 26 ),"
  done
else #more than 52
  for i in `seq 1 26`
  do
    echo "sd=sd${i},lun=/dev/sd`chr $( expr $i + 96 )`,openflags=o_direct,hitarea=0,range=(0,$WORKING_SET)$THREADS_VAR" >> $FILENAME
    SD_VAR=$SD_VAR"sd$i,"
  done

  ADDITIONAL_DISK=$( expr $DISK_NUM - 52 )
  for i in `seq 1 26`
  do
    echo "sd=sd$( expr $i + 26 ),lun=/dev/sda`chr $( expr $i + 96 )`,openflags=o_direct,hitarea=0,range=(0,$WORKING_SET)$THREADS_VAR" >> $FILENAME
    SD_VAR=$SD_VAR"sd$( expr $i + 26 ),"
  done

  for i in `seq 1 $ADDITIONAL_DISK`
  do
    echo "sd=sd$( expr $i + 52 ),lun=/dev/sdb`chr $( expr $i + 96 )`,openflags=o_direct,hitarea=0,range=(0,$WORKING_SET)$THREADS_VAR" >> $FILENAME
    SD_VAR=$SD_VAR"sd$( expr $i + 52 ),"
  done

fi

SD_VAR="${SD_VAR%?}"

echo "wd=wd1,sd=($SD_VAR),xfersize=${BLOCK_SIZE},rdpct=${READ_PERCENT},seekpct=${RANDOM_PERCENT}"  >> $FILENAME

WARMUP_VAR=
if [[ ! -z $WARMUP_TIME ]]
then
  WARMUP_VAR=",warmup=$WARMUP_TIME"
fi

INTERVAL_VAR=
if [[ ! -z $INTERVAL_TIME ]]
then 
  INTERVAL_VAR=",interval=$INTERVAL_TIME"
fi

echo "rd=run1,wd=wd1${IORATE_VAR},elapsed=${TEST_TIME}${WARMUP_VAR}${INTERVAL_VAR}"  >> $FILENAME
