#!/usr/bin/ruby
require_relative "rvc-util.rb"
require_relative "util.rb"
require 'shellwords'

@log_file = "#{$log_path}/prevalidation/deploy-hcitvm"
@tvm_folder_path_escape, @tvm_folder_path_escape_gsub = _get_tvm_folder_path_escape
@hosts_list = _get_deploy_hosts_list
_get_cl_path
@vm_num = @hosts_list.size
@exit_code = 250
@no_failure = true
network_name_gsub = $network_name.gsub('"', '\"')
@get_network_instance_escape = Shellwords.escape(%{vsantest.perf.get_network_instance_by_name . "#{network_name_gsub}"})
ds_hosts_hash = {}
#decide deployment based on datastore
$datastore_names.each do |datastore_name|
  ds_hosts_hash[datastore_name] = _get_hosts_list_by_ds_name(datastore_name) & @hosts_list
end

temp_arr = []
ds_hosts_hash.keys.each do |ds|
  temp_hosts = ds_hosts_hash[ds].clone
  temp_hosts.each do |host|
    if temp_arr.include? host
      ds_hosts_hash[ds].delete(host)
    else
      temp_arr << host
    end
  end
end

temp_hash = ds_hosts_hash.clone
temp_hash.keys.each do |ds|
  if temp_hash[ds] == []
    ds_hosts_hash.delete(ds)
  end
end

def deployOnHost(datastore, vm_num, ip, host)
  ds_path = _get_ds_path_escape(datastore)[0]
  ds_path_gsub = ds_path.gsub('"', '\"')
  prefix = "hci-tvm-#{host}".gsub('"', '\"')

  if $static_enabled
    deploy_action_escape = Shellwords.escape(%{vsantest.perf.deploy_tvm . --resource-pool #{$resource_pool_name_escape} \
     --vm-folder #{$vm_folder_name} --datastore "#{ds_path_gsub}" --network ~dest_network --num-vms #{vm_num} \
     --name-prefix "#{prefix}" --static --ip #{ip} --ip-size #{$static_ip_size} --host "#{host}"})
  else
    deploy_action_escape = Shellwords.escape(%{vsantest.perf.deploy_tvm . --resource-pool #{$resource_pool_name_escape} \
      --vm-folder #{$vm_folder_name} --datastore "#{ds_path_gsub}" --network ~dest_network --num-vms #{vm_num} \
      --name-prefix "#{prefix}" --host "#{host}"})
  end
  log_file = @log_file + "-#{host}" + ".log"
  if !system("rvc #{$vc_rvc} --path #{$cl_path_escape} -c #{@get_network_instance_escape} -c #{deploy_action_escape} \
    -c 'exit' -q > #{log_file} 2>&1")
    failureCapture(`tail -1 #{log_file}`.chomp, log_file)
  end
end

def failureCapture(rcode,log_file)
  msg = ""
  case rcode
  when "255"
    msg = "Deployment failed"
    @no_failure = false
    @exit_code = rcode.to_i
  when "254"
    msg = "IP Assignment failed or IP not reachable"
    @no_failure = false
    @exit_code = rcode.to_i
  when "253"
    msg = "SSH to client VM failed"
    @no_failure = false
    @exit_code = rcode.to_i
  else
    msg = "Unknow Error"
  end
  puts msg, log_file
end

def createTvmFolder
  move_vms_action_escape = Shellwords.escape(%{mv hosts/*/vms/#{$tvm_prefix}-* #{@tvm_folder_path_escape}})
  puts `rvc #{$vc_rvc} -c "mkdir #{@tvm_folder_path_escape_gsub}" -c 'exit' -q`,@log_file
  puts `rvc #{$vc_rvc} --path #{$cl_path_escape} -c #{move_vms_action_escape} -c 'exit' -q`,@log_file
end

#load $cleanuptvmfile
if $static_enabled
  if $ip_pool == [] or $ip_pool.size < @vm_num
    ip_pool = _get_ip_pools
  else
    ip_pool = $ip_pool
  end
  if ip_pool.size < @vm_num
    puts ip_pool,@log_file
    puts "IP range(Size: #{ip_pool.size}) specified doesn't have enough available IPs for #{@vm_num} of VMs",@log_file
    exit(251)
  end
else
  ip_pool = [0] * @vm_num
end

arr_node = []
ds_hosts_hash.keys.each do |ds|
  ds_hosts_hash[ds].each do |host|
    arr_node << Thread.new(ds,1,ip_pool[0],host){|p1,p2,p3,p4| deployOnHost(p1,p2,p3,p4)}
    ip_pool = ip_pool.drop(1)
  end
end

arr_node.each{|t| t.join}
createTvmFolder

if !@no_failure
  exit(@exit_code)
end