#!/bin/bash
if [ $# -eq 0 ]; then
   clear
   echo "****************************************************"
   echo "*** Convert HCMT output into HWCCT output format ***"
   echo "****************************************************"
   echo
   echo "How to use is simple:"
   echo
   echo "./cnv_hcmt_hwcct.sh <full path to HCMT zip file> <path to output directory> <name to replace localhost>"
   echo
   echo "Example:"
   echo "./cnv_hcmt_hwcct.sh /SAPShare/HCMT/setup/hcmtresult-20190711103036.zip ./DISK"
   exit
fi
#
# Cleanup
#
rm -rf $2
mkdir -p $2/tmp
#
# Extract the FS Read resluts from input zip Archive
#
unzip -p $1 Results/168B7333-86D4-1334-A300F54B104B6ADB.json > $2/tmp/fsread.results 2>/dev/null
sed -i "s/localhost/$3/g" $2/tmp/fsread.results
#
# Extract the FS Write results from input zip Archive
#
unzip -p $1 Results/D664D001-933D-41DE-A904F304AEB67906.json > $2/tmp/fswrite.results 2>/dev/null
sed -i "s/localhost/$3/g" $2/tmp/fswrite.results
#
# determine number of hosts tested
#
fsread_content=`cat $2/tmp/fsread.results | wc -l`
if [ $fsread_content -ne "0" ]
then
  nbr_hosts=`jq '.Measures[].ExecutionVariant.Host' $2/tmp/fsread.results | awk '! ($0 in X) { X[$0]; print }' | wc -l`
else
  nbr_hosts=`jq '.Measures[].ExecutionVariant.Host' $2/tmp/fswrite.results | awk '! ($0 in X) { X[$0]; print }' | wc -l`
fi
#echo "Number of hosts:" $nbr_hosts
max_index=`expr $nbr_hosts - 1`
#echo "Max Index:" $max_index
#
# store hostnames into the hostnames array
#
if [ $fsread_content -ne "0" ]
then
  mapfile -t hn < <(jq '.Measures[].ExecutionVariant.Host' $2/tmp/fsread.results | sort -u)
else
  mapfile -t hn < <(jq '.Measures[].ExecutionVariant.Host' $2/tmp/fswrite.results | sort -u)
fi

for i in `seq 0 $max_index`; do
    hn[$i]=`echo "${hn[$i]}" | tr -d '"'`
    #echo ${hn[$i]}
done
#
# now collect all results and store them into an array
#
mapfile -t l4kiw < <(jq '.Measures[] | select(.ExecutionVariant.Description == "4K Block, Log Volume 1GB, Sequential") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do l4kiw[$i]=`printf '%.*f\n' 3 ${l4kiw[$i]}`;done
mapfile -t l4kow < <(jq '.Measures[] | select(.ExecutionVariant.Description == "4K Block, Log Volume 5GB, Overwrite") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do l4kow[$i]=`printf '%.*f\n' 3 ${l4kow[$i]}`;done
mapfile -t l4kl < <(jq '.Measures[] | select(.ExecutionVariant.Description == "4K Block, Log Volume 5GB, Overwrite") | .Results[].Latency' $2/tmp/fswrite.results)
mapfile -t l16kow < <(jq '.Measures[] | select(.ExecutionVariant.Description == "16K Block, Log Volume 16GB, Overwrite") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do l16kow[$i]=`printf '%.*f\n' 3 ${l16kow[$i]}`;done
mapfile -t l16kl < <(jq '.Measures[] | select(.ExecutionVariant.Description == "16K Block, Log Volume 16GB, Overwrite") | .Results[].Latency' $2/tmp/fswrite.results)
mapfile -t l1mow < <(jq '.Measures[] | select(.ExecutionVariant.Description == "1M Block, Log Volume 16GB, Overwrite") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do l1mow[$i]=`printf '%.*f\n' 3 ${l1mow[$i]}`;done
mapfile -t d16kiw < <(jq '.Measures[] | select(.ExecutionVariant.Description == "16KB Block, Data Volume 16GB") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do d16kiw[$i]=`printf '%.*f\n' 3 ${d16kiw[$i]}`;done
mapfile -t d64kiw < <(jq '.Measures[] | select(.ExecutionVariant.Description == "64KB Block, Data Volume 16GB") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do d64kiw[$i]=`printf '%.*f\n' 3 ${d64kiw[$i]}`;done
mapfile -t d1miw < <(jq '.Measures[] | select(.ExecutionVariant.Description == "1MB Block, Data Volume 16GB") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do d1miw[$i]=`printf '%.*f\n' 3 ${d1miw[$i]}`;done
mapfile -t d16miw < <(jq '.Measures[] | select(.ExecutionVariant.Description == "16MB Block, Data Volume 16GB") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do d16miw[$i]=`printf '%.*f\n' 3 ${d16miw[$i]}`;done
mapfile -t d64miw < <(jq '.Measures[] | select(.ExecutionVariant.Description == "64MB Block, Data Volume 16GB") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do d64miw[$i]=`printf '%.*f\n' 3 ${d64miw[$i]}`;done
mapfile -t d16kow < <(jq '.Measures[] | select(.ExecutionVariant.Description == "16KB Block, Data Volume 16GB, Overwrite") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do d16kow[$i]=`printf '%.*f\n' 3 ${d16kow[$i]}`;done
mapfile -t d64kow < <(jq '.Measures[] | select(.ExecutionVariant.Description == "64KB Block, Data Volume 16GB, Overwrite") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do d64kow[$i]=`printf '%.*f\n' 3 ${d64kow[$i]}`;done
mapfile -t d1mow < <(jq '.Measures[] | select(.ExecutionVariant.Description == "1MB Block, Data Volume 16GB, Overwrite") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do d1mow[$i]=`printf '%.*f\n' 3 ${d1mow[$i]}`;done
mapfile -t d16mow < <(jq '.Measures[] | select(.ExecutionVariant.Description == "16MB Block, Data Volume 16GB, Overwrite") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do d16mow[$i]=`printf '%.*f\n' 3 ${d16mow[$i]}`;done
mapfile -t d64mow < <(jq '.Measures[] | select(.ExecutionVariant.Description == "64MB Block, Data Volume 16GB, Overwrite") | .Results[].ThroughputIO' $2/tmp/fswrite.results)
for i in `seq 0 $max_index`; do d64mow[$i]=`printf '%.*f\n' 3 ${d64mow[$i]}`;done
mapfile -t l4kr < <(jq '.Measures[] | select(.ExecutionVariant.Description == "4KB Block, Log Volume 5GB, Read") | .Results[].ThroughputIO' $2/tmp/fsread.results)
for i in `seq 0 $max_index`; do l4kr[$i]=`printf '%.*f\n' 3 ${l4kr[$i]}`;done
mapfile -t l16kr < <(jq '.Measures[] | select(.ExecutionVariant.Description == "16KB Block, Log Volume 16GB, Read") | .Results[].ThroughputIO' $2/tmp/fsread.results)
for i in `seq 0 $max_index`; do l16kr[$i]=`printf '%.*f\n' 3 ${l16kr[$i]}`;done
mapfile -t l1mr < <(jq '.Measures[] | select(.ExecutionVariant.Description == "1MB Block, Log Volume 16GB, Read") | .Results[].ThroughputIO' $2/tmp/fsread.results)
for i in `seq 0 $max_index`; do l1mr[$i]=`printf '%.*f\n' 3 ${l1mr[$i]}`;done
mapfile -t d64kr < <(jq '.Measures[] | select(.ExecutionVariant.Description == "64KB Block, Data Volume 16GB, Read") | .Results[].ThroughputIO' $2/tmp/fsread.results)
for i in `seq 0 $max_index`; do d64kr[$i]=`printf '%.*f\n' 3 ${d64kr[$i]}`;done
mapfile -t d1mr < <(jq '.Measures[] | select(.ExecutionVariant.Description == "1MB Block, Data Volume 16GB, Read") | .Results[].ThroughputIO' $2/tmp/fsread.results)
for i in `seq 0 $max_index`; do d1mr[$i]=`printf '%.*f\n' 3 ${d1mr[$i]}`;done
mapfile -t d16mr < <(jq '.Measures[] | select(.ExecutionVariant.Description == "16MB Block, Data Volume 16GB, Read") | .Results[].ThroughputIO' $2/tmp/fsread.results)
for i in `seq 0 $max_index`; do d16mr[$i]=`printf '%.*f\n' 3 ${d16mr[$i]}`;done
mapfile -t d64mr < <(jq '.Measures[] | select(.ExecutionVariant.Description == "64MB Block, Data Volume 16GB, Read") | .Results[].ThroughputIO' $2/tmp/fsread.results)
for i in `seq 0 $max_index`; do d64mr[$i]=`printf '%.*f\n' 3 ${d64mr[$i]}`;done
#
# Control
#
if [[ -n ${l4kiw[0]} ]] && [ ${l4kiw[0]} != 0.000 ]; then 
  echo "Log, 4K initial write"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${l4kiw[$i]};done;
fi
if [[ -n ${l4kow[0]} ]] && [ ${l4kow[0]} != 0.000 ]; then 
  echo "Log, 4K overwrite"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${l4kow[$i]};done;
fi
if [[ -n ${l4kl[0]} ]] && [ ${l4kl[0]} != 0.000 ]; then 
  echo "Log, 4K latency"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${l4kl[$i]};done;
fi
if [[ -n ${l16kow[0]} ]] && [ ${l16kow[0]} != 0.000 ]; then 
  echo "Log, 16K overwrite"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${l16kow[$i]};done;
fi
if [[ -n ${l16kl[0]} ]] && [ ${l16kl[0]} != 0.000 ]; then 
  echo "Log, 16K latency"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${l16kl[$i]};done;
fi
if [[ -n ${l1mow[0]} ]] && [ ${l1mow[0]} != 0.000 ]; then 
  echo "Log, 1M overwrite"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${l1mow[$i]};done;
fi
if [[ -n ${l1mr[0]} ]] && [ ${l1mr[0]} != 0.000 ]; then 
  echo "Log, 1M read"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${l1mr[$i]};done;
fi
if [[ -n ${d16kiw[0]} ]] && [ ${d16kiw[0]} != 0.000 ]; then 
  echo "Data, 16K initial write"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d16kiw[$i]};done;
fi
if [[ -n ${d16kow[0]} ]] && [ ${d16kow[0]} != 0.000 ]; then 
  echo "Data, 16K overwrite"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d16kow[$i]};done;
fi
if [[ -n ${d64kiw[0]} ]] && [ ${d64kiw[0]} != 0.000 ]; then 
  echo "Data, 64K initial write"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d64kiw[$i]};done;
fi
if [[ -n ${d64kow[0]} ]] && [ ${d64kow[0]} != 0.000 ]; then 
  echo "Data, 64K overwrite"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d64kow[$i]};done;
fi
if [[ -n ${d64kr[0]} ]] && [ ${d64kr[0]} != 0.000 ]; then 
  echo "Data, 64K read"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d64kr[$i]};done;
fi
if [[ -n ${d1miw[0]} ]] && [ ${d1miw[0]} != 0.000 ]; then 
  echo "Data, 1M initial write"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d1miw[$i]};done;
fi
if [[ -n ${d1mow[0]} ]] && [ ${d1mow[0]} != 0.000 ]; then 
  echo "Data, 1M overwrite"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d1mow[$i]};done;
fi
if [[ -n ${d1mr[0]} ]] && [ ${d1mr[0]} != 0.000 ]; then 
  echo "Data, 1M read"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d1mr[$i]};done;
fi
if [[ -n ${d16miw[0]} ]] && [ ${d16miw[0]} != 0.000 ]; then 
  echo "Data, 16M initial write"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d16miw[$i]};done;
fi
if [[ -n ${d16mow[0]} ]] && [ ${d16mow[0]} != 0.000 ]; then 
  echo "Data, 16M overwrite"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d16mow[$i]};done;
fi
if [[ -n ${d16mr[0]} ]] && [ ${d16mr[0]} != 0.000 ]; then 
  echo "Data, 16M read"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d16mr[$i]};done;
fi
if [[ -n ${d64miw[0]} ]] && [ ${d64miw[0]} != 0.000 ]; then 
  echo "Data, 64M initial write"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d64miw[$i]};done;
fi
if [[ -n ${d64mow[0]} ]] && [ ${d64mow[0]} != 0.000 ]; then 
  echo "Data, 64M overwrite"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d64mow[$i]};done;
fi
if [[ -n ${d64mr[0]} ]] && [ ${d64mr[0]} != 0.000 ]; then 
  echo "Data, 64M read"
  for i in `seq 0 $max_index`; do echo ${hn[$i]} ${d64mr[$i]};done;
fi
#
# now create the output files
#for i in `seq 0 $max_index`; do
#    cp contention_log_template $2/$nbr_hosts"_contention_log_"${hn[$i]}
#    cp contention_data_template $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%l4kow%/${l4kow[$i]}/g" $2/$nbr_hosts"_contention_log_"${hn[$i]}
#    sed -i "s/%l4kl%/${l4kl[$i]}/g" $2/$nbr_hosts"_contention_log_"${hn[$i]}
#    sed -i "s/%l16kow%/${l16kow[$i]}/g" $2/$nbr_hosts"_contention_log_"${hn[$i]}
#    sed -i "s/%l4kl%/${l4kl[$i]}/g" $2/$nbr_hosts"_contention_log_"${hn[$i]}
#    sed -i "s/%l16kl%/${l16kl[$i]}/g" $2/$nbr_hosts"_contention_log_"${hn[$i]}
#    sed -i "s/%l1mow%/${l1mow[$i]}/g" $2/$nbr_hosts"_contention_log_"${hn[$i]}
#    sed -i "s/%l1mr%/${l1mr[$i]}/g" $2/$nbr_hosts"_contention_log_"${hn[$i]}
#    sed -i "s/%d16kiw%/${d16kiw[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d16kow%/${d16kow[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d64kiw%/${d64kiw[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d64kow%/${d64kow[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d64kr%/${d64kr[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d1miw%/${d1miw[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d1mow%/${d1mow[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d1mr%/${d1mr[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d16miw%/${d16miw[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d16mow%/${d16mow[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d16mr%/${d16mr[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d64miw%/${d64miw[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d64mow%/${d64mow[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#    sed -i "s/%d64mr%/${d64mr[$i]}/g" $2/$nbr_hosts"_contention_data_"${hn[$i]}
#done
#echo "Done. Output files in" $2
exit 0
