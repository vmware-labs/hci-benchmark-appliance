#!/bin/sh

Exit() {
   echo 'TEST RUN COMPLETE: ' $1
   if [[ "$1" == "PASSED" ]]; then
      if [[ -d ${tmpDir} ]]; then
         rm -rf ${tmpDir}
      fi
      exit 0
   else
      exit 1
   fi
}

# Create tmp test directory
tmpDir=/tmp/esxcliUnitTest-$$
mkdir -p ${tmpDir}
if [[ ! -d ${tmpDir} ]]; then
   echo "Failed to create tmp directory"
   Exit 'FAIL'
fi

# Define harmless errors for auto test
harmlessErrorList=${tmpDir}/harmlessErrorList.txt
echo " Missing required parameter " > $harmlessErrorList
echo " Must specify one of " >> $harmlessErrorList

# Define exclusion list for auto test
errorExcludeList=${tmpDir}/errorExcludeList.txt
rm -f $excludeList
cp -f $harmlessErrorList $errorExcludeList
echo " ERROR\] [a-zA-Z]" >> $errorExcludeList
echo " INFO\]" >> $errorExcludeList

CheckError() {
   if [[ -f $esxcliLogFile ]]; then
      if [ `fgrep -v ' INFO]' $esxcliLogFile | wc -l` != 0 ]; then
         # Dump all error (even if they are harmless)
         if [ `egrep -v -f $errorExcludeList $esxcliLogFile | wc -l` == 0 ]; then
            # Some errors are not real error
            return
         fi
         # Dump log
         echo "Error: Dumping the last 100 lines of the log file ($esxcliLogFile)..."
         tail -100 $esxcliLogFile
         Exit 'FAIL'
      fi
   fi
}

TestHelp() {
   # Print help test
   for cmd in "$esxcliCmd"; do
      $cmd --help
      CheckError
      $cmd esxcli --help
      CheckError
      $cmd esxcli command --help
      CheckError
      $cmd esxcli command list --help
      CheckError
      $cmd esxcli
      CheckError
      $cmd esxcli command
      CheckError
   done
}

TestSessionFile() {
   # Test save session file
   session=${tmpDir}/session.txt
   rm -f ${session}
   $esxcliCmd --savesessionfile=${session}
   if [ $? != 0 ]; then
      echo 'Failed to save session file'
      Exit 'FAIL'
   fi

   # Test use session file
   $esxcliCmd --sessionfile=${session}
   if [ $? != 0 ]; then
      echo 'Failed to use session file'
      Exit 'FAIL'
   fi

   # Test use session file with different server name than in cookie domain
   host=`python -c "import socket; print socket.gethostbyaddr('"$VI_SERVER"')[0]"`
   ip=`python -c "import socket; print socket.gethostbyaddr('"$VI_SERVER"')[2][-1]"`
   for serverName in $host $ip; do
      $esxcliCmd --server $serverName --sessionfile=${session} > /dev/null
      if [ $? != 0 ]; then
         echo 'Failed to use session file with addr alias'
         Exit 'FAIL'
      fi
   done
}

TestSessionEncoding() {
   # Bad encoding
   $esxcliCmd --encoding=foo --formatter=csv esxcli command list > /dev/null
   if [[ $? == 0 ]]; then
      echo "Failed to catch bad encoding"
      Exit 'FAIL'
   fi

   # Good encodings
   esxclicmdlist_xml=${tmpDir}/esxclicmdlist.xml
   encodings="utf8 utf-8 cp936 iso-8859-1 shiftjis"
   for encoding in $encodings; do
      $esxcliCmd --encoding=$encoding --formatter=xml esxcli command list > $esxclicmdlist_xml
      CheckError
      if [[ `head -1 $esxclicmdlist_xml | fgrep $encoding | wc -l` -ne 1 ]]; then
         echo "Failed to encode with encoding $encoding"
         Exit 'FAIL'
      fi
   done

   # xml encoding must default to utf-8
   if [[ `$esxcliCmd --formatter=xml esxcli command list | head -1 | fgrep -i "utf-8" | wc -l` -ne 1 ]]; then
      echo "Default xml encoding is not 'utf-8'"
      Exit 'FAIL'
   fi
}

TestXml() {
   testscript=${tmpDir}/testxml.py
   echo 'from xml.dom.minidom import parse' > $testscript
   echo 'dom1 = parse("'$1'")' >> $testscript
   $python $testscript
   if [ $? != 0 ]; then
      cat $1
      Exit 'FAIL'
   fi
}

if [[ -f /bin/vmware ]]; then
   # Visor
   esxcliCmd=/sbin/esxcli
   esxcliLogFile=/var/log/esxcli.log
   python=python
else
   # Remote host
   #
   # -s {server}
   # -u {user}
   # -p {password}
   # -t {thumbprint}
   server=voyager-106 # Default to use my ESXi :)
   user=root
   password=
   thumbprint=
   while getopts ":s:u:p:t:" optname; do
      case "$optname" in
         "s") server=$OPTARG ;;
         "u") user=$OPTARG ;;
         "p") password=$OPTARG ;;
         "t") thumbprint=$OPTARG ;;
         *) echo "Unknown option: $OPTARG" ;;
      esac
   done

   currBora=`pwd | sed 's/$/\//;s/.*\/bora\//& &/;s/\/bora.*/\//;s/ .*//'`'bora'
   esxcliCmd="$currBora/vim/py/py.sh $currBora/vim/py/esxcli/esxcli.py"
   esxcliLogFile=`pwd`/esxcli.py.log
   if [[ "$VMBLD" == "" ]]; then
      export VMBLD=beta
   fi
   export VI_SERVER=${server}
   export VI_USERNAME=${user}
   export VI_PASSWORD=${password}
   export VI_THUMBPRINT=${thumbprint}
   python=/build/toolchain/lin32/python-2.6.1/bin/python

   # Test session file
   TestSessionFile

   # Test session encoding
   TestSessionEncoding
fi

# Setup
if [[ -f $esxcliLogFile ]]; then
   rm -f $esxcliLogFile
fi

# Do help test
TestHelp

# Make sure it can be piped through more
$esxcliCmd esxcli command list | echo 'q' | more
CheckError

# Create batch cmd file
esxclicmdlist=${tmpDir}/esxclicmdlist.txt
$esxcliCmd --formatter=csv --format-param "fields=Namespace,Command" --format-param "show-header=false" esxcli command list > $esxclicmdlist
CheckError

# Only test list / get cmd
testbatch=${tmpDir}/testbatch.txt
fgrep list $esxclicmdlist | sed 's/[,.]/ /g' > $testbatch
fgrep get $esxclicmdlist | sed 's/[,.]/ /g' >> $testbatch

# Testing the script
# Exclude some known command we cannot do
excludeList=${tmpDir}/excludeList.txt
rm -f $excludeList
# XXX: Skip this as get always fail
echo "iscsi ibftboot get" >> $excludeList
# XXX: Storage raid /san are completely broken
echo "storage raid" >> $excludeList
echo "storage san" >> $excludeList
# XXX: This is throwing a strange exception
echo "software sources vib get" >> $excludeList
# Echo back which tests to skip
echo ""
echo "Excluding the following broken esxcli commands..."
cat $excludeList
egrep -v -f $excludeList $testbatch > ${testbatch}.tmp
cp -f ${testbatch}.tmp $testbatch

# Define formatters to test
formatters="simple table html xml keyvalue json python csv"

# Test with batch mode
doBatchTest=0 # Set to 1 to enable batch test
if [[ $doBatchTest == 1 ]]; then
   echo ""
   echo "Running batch test..."
   suffixLine="=================================================================="
   batchParams="--batch-param continueOnError=true --batch-param printCommand=true --batch-param resultSuffixLine=${suffixLine}"
   for formatter in $formatters ; do
      $esxcliCmd --debug --formatter ${formatter} --batch $testbatch ${batchParams} > /dev/null
      CheckError
   done
fi

# Run one cmd at a time
# ***** SLOW *****
#
# XXX: Test format parameters
#formatParams="--format-param fields=Device --format-param show-header=false"
echo ""
echo "Running esxcli test..."
formatParams=
testresult=${tmpDir}/testresult.txt
for formatter in $formatters ; do
   for clicmd in `sed 's/ /@/g' $testbatch`; do
      # Same as ${clicmd//@/ }
      clicmd=`echo ${clicmd} | sed 's/@/ /g'`
      cmd="$esxcliCmd --debug --formatter ${formatter} ${formatParams} ${clicmd}"
      echo $cmd
      `$cmd > $testresult`
      CheckError
      if [[ ! -f $esxcliLogFile ]]; then
         if [[ $(cat $testresult | fgrep -c "Missing required parameter") > 0 ]]; then
            continue
         fi
      fi

      if [[ -s $testresult ]]; then
         # Skip harmless errors
         if [[ ! -f $esxcliLogFile ]] || [ `fgrep -f $harmlessErrorList $esxcliLogFile | wc -l ` == 0 ]; then
            case $formatter in
            "python" )
               testscript=${tmpDir}/testpython.py
               echo 'with open("'$testresult'") as fp:' > $testscript
               echo '   eval(fp.read())' >> $testscript
               $python $testscript
               if [ $? != 0 ]; then
                  cat $testresult
                  Exit 'FAIL'
               fi
               ;;
            "json" )
               testscript=${tmpDir}/testjson.py
               echo 'try:' > $testscript
               echo '   import json' >> $testscript
               echo '   with open("'$testresult'") as fp:' >> $testscript
               echo '      json.load(fp)' >> $testscript
               echo 'except ImportError:' >> $testscript
               echo '   print("No json module. Skipped json verification")' >> $testscript
               $python $testscript
               if [ $? != 0 ]; then
                  cat $testresult
                  Exit 'FAIL'
               fi
               ;;
            "html" )
               testresult1=${tmpDir}/testresult1.txt
               echo "<top>" > $testresult1
               cat ${testresult} >> $testresult1
               echo "</top>" >> $testresult1

               TestXml $testresult1
               ;;
            "csv" )
               testscript=${tmpDir}/testcsv.py
               echo 'try:' > $testscript
               echo '   import csv' >> $testscript
               echo '   reader = csv.reader(open("'$testresult'", "rb"))' >> $testscript
               echo '   for row in reader:' >> $testscript
               #echo '      print row' >> $testscript
               echo '      x = row' >> $testscript
               echo 'except ImportError:' >> $testscript
               echo '   print("No csv module. Skipped csv verification")' >> $testscript
               $python $testscript
               if [ $? != 0 ]; then
                  cat $testresult
                  Exit 'FAIL'
               fi
               ;;
            esac
         fi
      fi
   done
done

Exit 'PASSED'
