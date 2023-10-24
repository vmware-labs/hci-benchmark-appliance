#!/bin/bash

export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/var/opt/OpenJDK-1.8.0.92-bin/bin:/var/opt/OpenJDK-1.8.0.92-bin/jre/bin
export HOME=/root

NUM_VM=$1
DIR=/opt/automation/tmp
SHORT=0
IP=`ifconfig eth0 2>/dev/null|awk '/inet addr:/ {print $2}'|sed 's/addr://'`
VERSION="vdbench50406"
STDDEVOFFSET=0
basedir=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
pushd $DIR

args=("$@")

#ELEMENTS is datastore name
ELEMENTS=${#args[@]}

rm -rf "$NUM_VM"*res.txt

for (( j=1;j<$ELEMENTS;j++)); do

    store_name=${args[${j}]}
    VM_NUM=$(ls "$NUM_VM"/*"$store_name"*txt | wc -l)

    max=1
    file_name=
    for file in "${NUM_VM}"/*"${store_name}"*txt
    do
        cur=$(grep 'RD' "${file}" | wc -l)
        if [ $cur -gt $max ]
        then
            max=$cur
            file_name=$file
        fi
    done
    if [ -z "$file_name" ]
    then
      file_name=$file
    fi
    echo "Datastore:  $store_name" | tee -a "$NUM_VM"-res.txt
    echo "=============================" | tee -a "$NUM_VM"-res.txt
    for i in `seq 1 $max`
    do
        if [ `grep -h ' avg' "$NUM_VM"/*"$store_name"*txt | sed "${i}q;d" | wc -l` != 0 ];then
            SHORT=1
        fi
        rm -rf /opt/automation/tmp/badfile.txt
        rm -rf iops_"$store_name".txt
        rm -rf tput_"$store_name".txt
        rm -rf lat_"$store_name".txt
        rm -rf rlat_"$store_name".txt
        rm -rf wlat_"$store_name".txt
        rm -rf p95_"$store_name".txt
        echo -n "(" > lat_"$store_name".txt
        echo -n "(" > rlat_"$store_name".txt
        echo -n "(" > wlat_"$store_name".txt
        echo -n "(" > p95_"$store_name".txt

        NUM=$(ls "$NUM_VM"/*"$store_name"*txt | wc -l)
        for f in "$NUM_VM"/*"$store_name"*txt
        do
            VERSION=`grep 'Vdbench distribution' "$f" | awk '{print $3}'`
            if [ $VERSION == "vdbench50407" ];then
                STDDEVOFFSET=1
            fi

            #check if the file has that valid line
            if [ `grep -h avg "$f" | sed "${i}q;d" | wc | awk '{print $1}'` != 0 ]
            then
                it=$(grep -h avg "$f" | sed "${i}q;d" | awk -v col_num=$(( 2 + $SHORT )) '{print $col_num}')
                printf "%f+" $it >> iops_"$store_name".txt

                it=$(grep -h avg "$f" | sed "${i}q;d" | awk -v col_num=$(( 3 + $SHORT )) '{print $col_num}')
                printf "%f+" $it >> tput_"$store_name".txt

                it=$(grep -h avg "$f" | sed "${i}q;d" | awk -v col_num=$(( 6 + $SHORT )) '{print $col_num}')
                printf "%f+" $it >> lat_"$store_name".txt

                it=$(grep -h avg "$f" | sed "${i}q;d" | awk -v col_num=$(( 7 + $SHORT )) '{print $col_num}')
                printf "%f+" $it >> rlat_"$store_name".txt

                it=$(grep -h avg "$f" | sed "${i}q;d" | awk -v col_num=$(( 8 + $SHORT )) '{print $col_num}')
                printf "%f+" $it >> wlat_"$store_name".txt

                it=$(grep -h avg "$f" | sed "${i}q;d" | awk -v col_num=$(( 10 + $SHORT + STDDEVOFFSET )) '{print $col_num}')
                printf "%f+" $it >> p95_"$store_name".txt
            else
                echo "  https://${IP}:8443/output/results/"`echo "${f}" | cut -d '/' -f5-` >> /opt/automation/tmp/badfile.txt 
                NUM=$((${NUM}-1))
            fi
        done

        echo 0 >> iops_"$store_name".txt
        IOPS=$(printf "%.2f" $(cat iops_"$store_name".txt  | bc))
    
        echo 0 >> tput_"$store_name".txt
        TPUT=$(printf "%.2f" $(cat tput_"$store_name".txt  | bc))
    
        echo "0) / ${NUM} " >> lat_"$store_name".txt
        LAT=$(printf "%.4f" $(cat lat_"$store_name".txt  | bc -l ))
    
        echo "0) / ${NUM}" >> rlat_"$store_name".txt
        RLAT=$(printf "%.4f" $(cat rlat_"$store_name".txt  | bc -l ))
        
        echo "0) / ${NUM}" >> wlat_"$store_name".txt
        WLAT=$(printf "%.4f" $(cat wlat_"$store_name".txt  | bc -l ))
    
        echo "0) / ${NUM}" >> p95_"$store_name".txt
        P95=$(printf "%.4f" $(cat p95_"$store_name".txt  | bc -l ))
    
        RD=$(grep RD "$file_name" | sed "${i}q;d" | cut -d ' ' -f3- )

        CPU_USAGE=`/opt/automation/lib/getCpuUsage.rb "$NUM_VM"`
        RAM_USAGE=`/opt/automation/lib/getRamUsage.rb "$NUM_VM"`
        echo "Version:    $VERSION" | tee -a "$NUM_VM"-res.txt
        echo "Run Def:    $RD" | tee -a "$NUM_VM"-res.txt
        echo "VMs         = $NUM" | tee -a "$NUM_VM"-res.txt
        echo "IOPS        = $IOPS IO/s" | tee -a "$NUM_VM"-res.txt
        echo "THROUGHPUT  = $TPUT MB/s" | tee -a "$NUM_VM"-res.txt
        echo "LATENCY     = $LAT ms" | tee -a "$NUM_VM"-res.txt
        echo "R_LATENCY   = $RLAT ms" | tee -a "$NUM_VM"-res.txt
        echo "W_LATENCY   = $WLAT ms" | tee -a "$NUM_VM"-res.txt
        echo "95%tile_LAT = $(printf "%.4f" `echo "$P95 * 1.645 + $LAT" | bc -l`) ms" | tee -a "$NUM_VM"-res.txt
    
        if [ $VM_NUM -gt $NUM ]
        then
          echo "Testing is done, $NUM out of $VM_NUM VMs finished test successfully. Please check following files for details:" | tee -a "$NUM_VM"-res.txt
          cat /opt/automation/tmp/badfile.txt | tee -a "$NUM_VM"-res.txt
        fi
        echo "=============================" | tee -a "$NUM_VM"-res.txt

        rm -rf /opt/automation/tmp/*.txt
    done
done

echo "Resource Usage:" | tee -a "$NUM_VM"-res.txt
echo "CPU USAGE  = $CPU_USAGE" | tee -a "$NUM_VM"-res.txt
echo "RAM USAGE  = $RAM_USAGE" | tee -a "$NUM_VM"-res.txt
VSAN_PCPU_USAGE=`/opt/automation/lib/getPCpuUsage.rb "$NUM_VM"`
if [ $? == 0 ]
  then
  echo "vSAN PCPU USAGE = $VSAN_PCPU_USAGE" | tee -a "$NUM_VM"-res.txt
fi

if [ -f "$NUM_VM"/performance_diag_result.html ]; then
    echo "=============================" | tee -a "$NUM_VM"-res.txt
    DIR_NAME=`basename "$NUM_VM"`
    echo "If you are interested in improving the IOPS/THROUGHPUT/LATENCY, please find the details in file performance_diag_result.html in directory ${DIR_NAME} " | tee -a "$NUM_VM"-res.txt
fi

rm -rf /opt/automation/tmp/*.txt
cd "$NUM_VM"
HCIBench_Version=`cat /etc/hcibench_version`
mkdir logs
cp -r /opt/automation/logs/ "$NUM_VM"/logs
tar zcfP HCIBench-${HCIBench_Version}-logs.tar.gz -C logs .
rm -rf logs
