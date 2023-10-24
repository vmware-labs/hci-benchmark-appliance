if [ $# != 1 ]
then
   echo Usage: $0 stats_log_file_name
   exit 1
fi
grep -v 'process = ' $1 |  sed 's/.*VmSize: \(.*\) kB,VmLck:.*VmRSS: \(.*\) kB,VmData:.*FDs: \(.*\),%CPU:\(.*\)/\1,\2,\3,\4/g' 
