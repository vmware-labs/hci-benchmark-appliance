if [ -z "$1" ]
then
   echo Usage: $0 process_name
   exit 1
fi
pid=`pidof "$1"`
if [ -z "$pid" ]
then
   echo Error\! "$1"\'s PID could not be found
   exit 1
fi
echo "$1" process = $pid
while true
do
vminfo=`cat /proc/"$pid"/status | grep Vm | tr '\n' ' '| sed 's/.*VmSize:\(.*\) kB VmLck:.*VmRSS:\(.*\) kB VmData:.*/\1 \2/g' | awk '{print $1*1024, $2*1024}' | sed -e's/^/"/' -e's/ /","/' -e 's/$/"/'`
cpu=`ls /proc/"$pid"/fd | wc -l`\",\"`top b n 1 p "$pid"  | grep "$pid"'.*'"$1" | awk '{print $9}'`
echo \"`date +'%x %X %s'`\",$vminfo,\"$cpu\"
sleep 30
done
