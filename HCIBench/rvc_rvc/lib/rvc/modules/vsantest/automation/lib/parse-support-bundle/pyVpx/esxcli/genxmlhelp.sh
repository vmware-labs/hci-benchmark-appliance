#!/bin/sh
#set -x

Usage() {
   echo "Usage: $0 [-s {server}] [-u {user}] [-p {password}]"
}

server=
user=
password=
if [ -f /bin/vmware ]; then
   esxcliCmd=/sbin/esxcli
else
   # Remote host
   #
   # -s {server}
   # -u {user}
   # -p {password}
   while getopts ":s:u:p:" optname; do
      case "$optname" in
         "s") server="$OPTARG" ;;
         "u") user="$OPTARG" ;;
         "p") password="$OPTARG" ;;
         *) echo "Unknown option: $OPTARG" ;;
      esac
   done

   if [ "$server" == "" ]; then
      Usage
      exit
   fi

   currBora=`pwd | sed 's/$/\//;s/.*\/bora\//& &/;s/\/bora.*/\//;s/ .*//'`'bora'
   esxcliCmd="$currBora/vim/py/py.sh $currBora/vim/py/esxcli/esxcli.py"
   if [ "$VMBLD" == "" ]; then
      export VMBLD=beta
   fi
   export VI_SERVER=${server}
   export VI_USERNAME=${user}
   export VI_PASSWORD=${password}
fi

#tmpDir=/tmp/genxmlhelp
#mkdir -p ${tmpDir}
#if [ ! -d ${tmpDir} ]; then
#   echo "Failed to create tmp directory ${tmpDir}"
#   exit
#fi

echo '<?xml version="1.0" encoding="utf-8"?>'
echo '<output>'
echo '<root>'
echo '   <list type="structure">'
for cmd in `$esxcliCmd --formatter=csv --format-param "fields=Namespace,Object,Command" --format-param "show-header=false" esxcli command list | sort`; do
   ns_cmd=`echo $cmd | sed 's/[,.]/ /g'`
   $esxcliCmd --generate-xml-help $ns_cmd --help | sed 's/^/      /'
done
echo '   </list>'
echo '</root>'
echo '</output>'
