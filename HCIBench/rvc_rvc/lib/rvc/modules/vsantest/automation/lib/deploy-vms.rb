#!/usr/bin/ruby
require 'shellwords'
require_relative "rvc-util.rb"
require_relative "util.rb"

@log_file = "#{$log_path}/deploy.log"
`rm -rf #{@log_file}`
@hosts_list = _get_deploy_hosts_list
_get_cl_path
@folder_path_escape, @folder_path_escape_gsub = _get_folder_path_escape
@disk_size_var = "--datadisk-size-gb #{$size_data_disk} "
@disk_num_var = "--datadisk-num #{$number_data_disk} "
@network_var = %{--network "#{$network_name}" }

network_name_gsub = $network_name.gsub('"', '\"')
@get_network_instance_escape = Shellwords.escape(%{vsantest.perf.get_network_instance_by_name . "#{network_name_gsub}"})

ds_hosts_hash = {}
#decide deployment based on datastore

$datastore_names.each do |datastore_name|
  ds_hosts_hash[datastore_name] = _get_hosts_list_by_ds_name(datastore_name) & @hosts_list
end

@compliant_ds_ids = []
if $storage_policy and not $storage_policy.empty? and not $storage_policy.strip.empty?
  @compliant_ds_ids = _get_compliant_datastore_ids_escape
  if @compliant_ds_ids == []
    puts "Cant find the storage policy #{$storage_policy} or Can't find compliant datastore for policy #{$storage_policy}",@log_file
    exit(251)
  end
end

def deployOnHost(datastore, vm_num, batch, ips, hosts)
  multiwriter_param = ""
  multiwriter_param = "-w" if $multiwriter and not $easy_run
  ip_rvc = ""
  host_rvc = ""
  ips.each do |ip|
    ip_rvc += "--ip #{ip} "
  end
  hosts.each do |host|
    host_rvc += "--host '#{host}' "
  end
  storage_policy = ""
  if @compliant_ds_ids.include? _get_ds_id_by_name(datastore)
    storage_policy = $storage_policy
  end
  ds_prefix = _get_ds_id_by_name(datastore)
  ds_path = _get_ds_path_escape(datastore)[0]
  ds_path_gsub = ds_path.gsub('"', '\"')
  prefix = "#{$vm_prefix}-#{ds_prefix}-#{batch}".gsub('"', '\"')
  if $static_enabled
    deploy_action_escape = Shellwords.escape(%{vsantest.perf.deploy_test_vms . --resource-pool #{$resource_pool_name_escape} \
      --vm-folder #{$vm_folder_name} --datastore "#{ds_path_gsub}" --network ~dest_network #{@disk_size_var} #{@disk_num_var} \
      --num-vms #{vm_num} --num-cpu #{$num_cpu} --size-ram #{$size_ram} --name-prefix "#{prefix}" #{host_rvc} --static #{ip_rvc} --ip-size #{$static_ip_size} \
      --storage-policy "#{storage_policy}" --tool "#{$tool}" #{multiwriter_param}})
  else
    deploy_action_escape = Shellwords.escape(%{vsantest.perf.deploy_test_vms . --resource-pool #{$resource_pool_name_escape} \
     --vm-folder #{$vm_folder_name} --datastore "#{ds_path_gsub}" --network ~dest_network #{@disk_size_var} #{@disk_num_var} \
     --num-vms #{vm_num} --num-cpu #{$num_cpu} --size-ram #{$size_ram} --name-prefix "#{prefix}" #{host_rvc} --storage-policy "#{storage_policy}" --tool "#{$tool}" #{multiwriter_param}})
  end
  log = Shellwords.escape("#{$log_path}/#{datastore}-#{batch}-vm-deploy.log")
  `rvc #{$vc_rvc} --path #{$cl_path_escape} -c #{@get_network_instance_escape} -c #{deploy_action_escape} -c 'exit' >> #{log} 2>&1`
  rcode = $?.exitstatus
  checkReturnCode(rcode)
end

def createVmFolder
  move_vms_action_escape = Shellwords.escape(%{mv hosts/*/vms/#{$vm_prefix}-* #{@folder_path_escape}})
  puts `rvc #{$vc_rvc} -c "mkdir #{@folder_path_escape_gsub}" -c 'exit' -q`,@log_file
  puts `rvc #{$vc_rvc} --path #{$cl_path_escape} -c #{move_vms_action_escape} -c 'exit' -q`,@log_file
end

def checkReturnCode(rcode)
  if rcode == 0
  elsif rcode == 254
    puts "Unable to get IP addresses for VMs or ping the IPs",@log_file
    exit(254)
  elsif rcode == 255
    puts "Unable to connect ESXi host",@log_file
    exit(255)
  elsif rcode == 253
    puts "Deployment Error",@log_file
    exit(253)
  else
    puts "Unknown Error",@log_file
    exit(252)
  end
end

load $cleanupfile
arr_node = []
if $static_enabled
  ip_pools = _get_ip_pools.uniq
  if ip_pools.size < $vm_num
    puts ip_pools,@log_file
    puts "IP range(Size: #{ip_pools.size}) specified doesn't have enough available IPs for #{$vm_num} of VMs",@log_file
    exit(251)
  end
else
  ip_pools = [0] * $vm_num
end

puts "#{ip_pools.to_s}", @log_file
puts "#{ds_hosts_hash.to_s}", @log_file
ds_hosts_hash.keys.each do |ds|
  hosts_size = ds_hosts_hash[ds].size
  batch = [[($vms_perstore/hosts_size).ceil,1].max,hosts_size].min
  batch = 1 if $multiwriter
  # see if each batch the number of vm deployed is equal
  # num_batch_more != 0 means some batches has one more vm than other batches, and we have num_batch_more of batches should
  # deploy more vm(this kind of batch we deploy vm_num_batch_more vms), and the number of normal batch is num_batch_less(deploy vm_num_batch_less vms)
  # num_batch_more is number of batches with 1 more vm deployed
  num_batch_more = $vms_perstore % batch
  vm_num_batch_more = $vms_perstore / batch + 1 if num_batch_more > 0
  vm_num_batch_less = $vms_perstore / batch
  vm_num_deploy = 0
  for batch_index in 0...[batch,$vms_perstore].min
    if batch_index < num_batch_more
      vm_num_deploy = vm_num_batch_more
    else
      vm_num_deploy = vm_num_batch_less
    end
    arr_node << Thread.new(ds,vm_num_deploy,batch_index,ip_pools[0...vm_num_deploy], ds_hosts_hash[ds]){|p1, p2, p3, p4, p5| deployOnHost(p1, p2, p3, p4, p5)} if vm_num_deploy > 0
    ip_pools = ip_pools.drop(vm_num_deploy)
  end
end

arr_node.each{|t| t.join}
createVmFolder