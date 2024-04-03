require 'yaml'
require 'fileutils'
require 'timeout'
require 'shellwords'
require_relative "rvc-util.rb"
require_relative "util.rb"

@log_file = "#{$log_path}/easy-run.log"
host_num = _get_deploy_hosts_list.count
ftt = 1
policy_rule_map = {}
vsan_stats_hash = {}
policy_ftt = 1
policy_ftm = "RAID-1(Mirroring)-Performance"
ratio = 0.25
disk_init = "ZERO"
_test_time = 3600
_warmup_time = 1800
@dedup = 0

vsan_datastores = _get_vsandatastore_in_cluster
if vsan_datastores == {}
  puts "------------------------------------------------------------------------------",@log_file
  puts "vSAN Is Not Enabled in Cluster #{$cluster_name}!",@log_file
  puts "------------------------------------------------------------------------------",@log_file
  exit(255)
else
  local_vsan = ""
  vsan_datastore_names = vsan_datastores.keys & $datastore_names
  if vsan_datastore_names.empty?
    puts "------------------------------------------------------------------------------",@log_file
    puts "vSAN Datastore not specified!",@log_file
    puts "------------------------------------------------------------------------------",@log_file
    exit(255)
  end
  vsan_datastore_names.each do |vsan_datastore_name|
    if vsan_datastores[vsan_datastore_name]["local"]
      local_type = "Local"
      local_vsan = vsan_datastore_name
    else
      local_type = "Remote"
    end
    puts "vSAN #{local_type} Datastore Name: #{vsan_datastore_name}", @log_file
    if disk_init == "ZERO"
      temp_cluster = _get_vsan_cluster_from_datastore(vsan_datastore_name)
      vsan_stats_hash = _get_vsan_disk_stats(temp_cluster)
      @dedup = vsan_stats_hash["Dedupe Scope"]
      disk_init = "RANDOM" if @dedup != 0
    end
  end

  cluster_to_pick = $cluster_name
  #choose which datastore to pick to calculate the easy-run parameters
  vsan_datastore_name = ""
  if local_vsan != ""
    vsan_datastore_name = local_vsan
  else
    vsan_datastore_name = vsan_datastore_names[0]
    remote_cluster_name = _get_vsan_cluster_from_datastore(vsan_datastore_name)
    cluster_to_pick = remote_cluster_name
  end
  vsan_stats_hash = _get_vsan_disk_stats(cluster_to_pick)
  puts "Picking vSAN Datastore Name: #{vsan_datastore_name}", @log_file
  policy_name, rules = _get_vsan_default_policy(vsan_datastore_name)
  puts "vSAN Default Policy: #{policy_name} \n#{rules}", @log_file

  if $storage_policy and not $storage_policy.empty? and not $storage_policy.strip.empty?
    rules = _get_storage_policy_rules($storage_policy)
    puts "Self-defined policy: #{rules}", @log_file
  end

  spbm_rule_map = _get_policy_rule_map(rules)

  policy_pftt = spbm_rule_map["VSAN.hostFailuresToTolerate.hostFailuresToTolerate"] || "1"
  policy_sftt = spbm_rule_map["VSAN.subFailuresToTolerate.subFailuresToTolerate"] || "0"
  policy_csc = spbm_rule_map["VSAN.checksumDisabled.checksumDisabled"] || "false"
  policy_ftm = spbm_rule_map["VSAN.replicaPreference.replicaPreference"].split(" ")[-1] || "RAID-1(Mirroring)-Performance" if spbm_rule_map["VSAN.replicaPreference.replicaPreference"]
  
  #policy_vsan_type = spbm_rule_map["VSAN.storageType.storageType"].split(" ")[-1] if spbm_rule_map.has_key?("VSAN.storageType.storageType")
  policy_compression_svc = ""
  #policy_encryption_svc = ""

  #vsan2: no pref==!has_key?("VSAN.dataService.dataEncryption")==$cluster_setting, since policy can override cluster setting, this param is useless at this moment
  #if policy_rule_map.has_key?("VSAN.dataService.dataEncryption")
  #  policy_encryption_svc = policy_rule_map["VSAN.dataService.dataEncryption"].split(" ")[-1]
  #end

  #vsan2: no pref==!has_key("VSAN.dataService.spaceEfficiency")==comp-only only; no dd/c; dd/c; comp-only
  #vsan1: no pref==!has_key("VSAN.dataService.spaceEfficiency")==$cluster_setting;
  if policy_rule_map.has_key?("VSAN.dataService.spaceEfficiency")
    policy_compression_svc = policy_rule_map["VSAN.dataService.spaceEfficiency"].split(" ")[-1]
  elsif $vsan_version == 2
    policy_compression_svc = "Compression Only"
  end

  policy_ftt = ( policy_pftt.to_i + 1 ) * ( policy_sftt.to_i + 1 )
  ftt = policy_ftt.to_i  
end

total_cache_size = vsan_stats_hash["Total_Cache_Size"]
num_of_dg = vsan_stats_hash["Total number of Disk Groups"]
num_of_cap = vsan_stats_hash["Total number of Capacity Drives"]
total_capacity_size = vsan_stats_hash["Total_Capacity_Size"]
total_usable_capacity = vsan_stats_hash["Total_Usable_Capacity"]
#@dedup = vsan_stats_hash["Dedupe Scope"]
vsan_type = vsan_stats_hash["vSAN type"]

temp_cl_path, temp_cl_path_escape = _get_cl_path(cluster_to_pick)
witness = `rvc #{$vc_rvc} --path #{temp_cl_path_escape} -c 'vsantest.vsan_hcibench.cluster_info .' -c 'exit' -q | grep -E "^Witness Host:"`.chomp 

if $vsan_version == 1
  puts "
  vSAN Version: vSAN 1
  Total Cache Size: #{total_cache_size} 
  Total number of Disk Groups: #{num_of_dg}
  Total number of Capacity Drives: #{num_of_cap} 
  vSAN type: #{vsan_type} 
  Dedupe Scope: #{@dedup}", @log_file
else
  puts "
  vSAN Version: vSAN ESA 
  Total number of Drives: #{num_of_cap}
  Total Capacity: #{total_capacity_size} 
  Total Usable Capacity: #{total_usable_capacity}", @log_file
  disk_init = "RANDOM" if policy_compression_svc and policy_compression_svc.include?("Compression")
end

if $vsan_version == 1 and witness != ""
  puts "#{witness}", @log_file
  num_of_dg -= 1
end

if $vsan_version == 1 and vsan_type == "All-Flash"
  total_cache_size = [num_of_dg * 600,total_cache_size].min
  ratio = 0.75
elsif $vsan_version == 2
  #in this case, total_cache_size represents 1/3 of the total capacity even there's no cache disk
  total_cache_size = total_capacity_size/3
end

#Ensure the usage not more than 80% of the capacity
while (total_usable_capacity - total_cache_size) < (total_capacity_size * 0.2)
  total_cache_size = total_cache_size/2
end

ftt_amplification = ftt
if policy_ftm.include? "Capacity"
  ftt_amplification = 1.33 if ftt == 2
  ftt_amplification = 1.66 if ftt == 3
end

vm_deployed_size = total_cache_size * ratio / ftt_amplification
if $vsan_version == 1
  @vm_num = num_of_dg * 2 * $total_datastore
else
  @vm_num = host_num * 4 * $total_datastore
end

@data_disk_num = 8 #num_of_cap * 2 / vm_num

#if @vm_num % host_num != 0
#  @vm_num += (host_num - @vm_num % host_num)
#end

thread_num = 32 / @data_disk_num
@disk_size = [(vm_deployed_size / (@vm_num / $total_datastore * @data_disk_num)).floor,1].max
time = Time.now.to_i

pref = "hci-vdb"
if $tool == "fio"
  pref = "hci-fio"
end

vcpu = 4
size_ram = 8

`sed -i "s/^vm_prefix.*/vm_prefix: '#{pref}'/g" /opt/automation/conf/perf-conf.yaml`
`sed -i "s/^number_vm.*/number_vm: #{@vm_num}/g" /opt/automation/conf/perf-conf.yaml`
`sed -i "s/^number_cpu.*/number_cpu: #{vcpu}/g" /opt/automation/conf/perf-conf.yaml`
`sed -i "s/^size_ram.*/size_ram: #{size_ram}/g" /opt/automation/conf/perf-conf.yaml`
`sed -i "s/^number_data.*/number_data_disk: #{@data_disk_num}/g" /opt/automation/conf/perf-conf.yaml`
`sed -i "s/^size_data.*/size_data_disk: #{@disk_size}/g" /opt/automation/conf/perf-conf.yaml`
`sed -i "s/^warm_up_disk_before_.*/warm_up_disk_before_testing: '#{disk_init}'/g" /opt/automation/conf/perf-conf.yaml`
`rm -rf /opt/tmp/tmp* ; mkdir -m 755 -p /opt/tmp/tmp#{time}` 

devider = 4
if policy_csc == "true"
  devider = 1
end

gotodir = "cd /opt/automation/#{$tool}-param-files;"
executable = "fioconfig create"

if $tool == "vdbench"
  executable = "sh /opt/automation/generate-vdb-param-file.sh"
end

workloadParam = ""
for workload in $workloads
  case workload
  when "4k70r"
    workloadParam = " -n #{@data_disk_num} -w 100 -t #{thread_num} -b 4k -r 70 -s 100 -e #{_test_time} -m #{_warmup_time}"
  when "4k100r"
    workloadParam = " -n #{@data_disk_num} -w 100 -t #{thread_num} -b 4k -r 100 -s 100 -e #{_test_time} -m #{_warmup_time}"
  when "8k50r"
    workloadParam = " -n #{@data_disk_num} -w 100 -t #{thread_num} -b 8k -r 50 -s 100 -e #{_test_time} -m #{_warmup_time}"
  when "256k0r"
    workloadParam = " -n #{@data_disk_num} -w 100 -t #{thread_num/devider} -b 256k -r 0 -s 0 -e #{_test_time} -m #{_warmup_time}"
  end

  if disk_init == "RANDOM"
    if $tool == "fio"
      workloadParam = workloadParam + " -bc 50 -dp 50" 
    else
      workloadParam = workloadParam + " -c 2 -d 2"
    end
  end
  
  puts `#{gotodir + executable + workloadParam}`,@log_file
  `FILE=$(ls /opt/automation/#{$tool}-param-files/ -tr | grep -v / |tail -1); cp /opt/automation/#{$tool}-param-files/${FILE} /opt/tmp/tmp#{time}`
end

`sed -i "s/^self_defined_param.*/self_defined_param_file_path: '\\/opt\\/tmp\\/tmp#{time}' /g" /opt/automation/conf/perf-conf.yaml`
`sed -i "s/^output_path.*/output_path: 'easy-run-#{time}'/g" /opt/automation/conf/perf-conf.yaml`
`sed -i "s/^testing_duration.*/testing_duration:/g" /opt/automation/conf/perf-conf.yaml`
`sed -i "s/^cleanup_vm.*/cleanup_vm: false/g" /opt/automation/conf/perf-conf.yaml`
`sync; sleep 1`
`ruby #{$allinonetestingfile}`
`rm -rf /opt/tmp/tmp#{time}`
