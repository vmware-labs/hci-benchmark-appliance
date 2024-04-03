#!/usr/bin/ruby
require_relative "util.rb"
require_relative "rvc-util.rb"
require 'fileutils'
require 'timeout'

@folder_path_escape = _get_folder_path_escape[0]
@vsan_clusters = []
@verbose_mode = ""
@test_status_log = "#{$log_path}/test-status.log"
`cp -f #{$basedir}/../conf/perf-conf.yaml #{$basedir}/../logs/hcibench.cfg`
`sed -i '/username/d' #{$basedir}/../logs/hcibench.cfg`
`sed -i '/password/d' #{$basedir}/../logs/hcibench.cfg`

`mkdir -m 755 -p #{$output_path_dir}` if !File.directory?($output_path_dir)

def failure_handler(what_failed)
  puts "[ERROR] #{what_failed} Failed...",@test_status_log
  if $cleanup_vm
    puts "Deleting VMs If Deployed...",@test_status_log
    load $cleanupfile
    puts "VMs Deleted",@test_status_log
  else
    puts "VMs Preserved for Debugging Purpose, You Can Run /opt/automation/cleanup-vm.sh to Delete VMs Manually",@test_status_log
  end

  if $static_enabled and $cleanup_vm
    system("ifconfig -s eth1 0.0.0.0; ifconfig eth1 down; ifconfig eth1 up")
  end

  puts "Testing Failed, For Details Please Find Logs in /opt/automation/logs", @test_status_log
  puts "Please Cancel And Re-Run The Testing",@test_status_log
  while true
    sleep(600)
  end
end

#Check sdb space
@diskutil = `df /dev/sdb | grep sdb | awk '{print $5}' | cut -d "%" -f1`.to_i
if @diskutil > 85
  puts %{Your /dev/sdb usage is more than 85%, please clear it up by removing older testing results or execute \
    'find /var/lib/docker/volumes/ -name "vdbench" | xargs rm -rf' \
    'find /var/lib/docker/volumes/ -name "fio" | xargs rm -rf' \
    to remove historical grafana graphs}, @test_status_log
  failure_handler "Disk space utilization"
end

# if debug is on
# if perfsvc is off, turn it on
# 1. find master node
# 2. set interval to 60s
# 3. turn on verbose mode
if $vsan_debug
  @vsan_clusters = _get_all_vsan_clusters
  if not @vsan_clusters.empty?
    @vsan_clusters.each do |vsan_cluster|
      _start_perfsvc(vsan_cluster) if not _is_ps_enabled(vsan_cluster)
      cluster_master_node = _get_perfsvc_master_node(vsan_cluster)
      cmd_get_verbose_mode = "esxcli vsan perf get | grep Verbose | awk '{print $3}'"
      host_key = $hosts_credential.has_key?(cluster_master_node) ? cluster_master_node : $hosts_credential.keys[0]   
      host_username = $hosts_credential[host_key]["host_username"]
      host_password = $hosts_credential[host_key]["host_password"]

      if ssh_valid(cluster_master_node,host_username,host_password)
        @verbose_mode = ssh_cmd(cluster_master_node,host_username,host_password,cmd_get_verbose_mode).chomp
      end
      if @verbose_mode != "Enabled"
        puts "Set vSAN Performance Service to verbose mode in cluster #{vsan_cluster}", @test_status_log
        _set_perfsvc_verbose_mode(true,vsan_cluster)
      else
        puts "vSAN Performance Service verbose mode is Enabled by default in cluster #{vsan_cluster}, skip setting", @test_status_log
      end
      $perfsvc_master_nodes = $perfsvc_master_nodes | [cluster_master_node]
    end
  else
    failure_handler "vSAN not enabled!"
  end
  cmd_change_interval = "esxcli vsan perf set --interval=60; echo $?"  
  $perfsvc_master_nodes.each do |master_node|
    host_key = $hosts_credential.has_key?(master_node) ? master_node : $hosts_credential.keys[0]   
    host_username = $hosts_credential[host_key]["host_username"]
    host_password = $hosts_credential[host_key]["host_password"]

    puts "Setting vSAN Performance Service interval to 60s on #{master_node}", @test_status_log
    if ssh_valid(master_node,host_username,host_password)
      if ssh_cmd(master_node,host_username,host_password,cmd_change_interval).chomp == "0"
        puts "vSAN Performance Service interval is set to 60s on Performance Service master node: #{master_node} ", @test_status_log
      else
        puts "Failed to set vSAN Performance Service interval on Performance Service master node: #{master_node}", @test_status_log
      end
    end
  end
end

# Enable static if needed, with pre-defined ip prefix
if $static_enabled
  failure_handler "Static IP Range is not big enough" if not _range_big_enough
  system("ifconfig -s eth1 0.0.0.0")
  #just need to get eth1_ip
  ip_pool = _get_ip_pools.uniq
  failure_handler "Not Enough IP in the range specified" if $eth1_ip == ""
  system("ifconfig -s eth1 #{$eth1_ip}/#{$static_ip_size}")
end

if !$reuse_vm or !system("ruby #{$healthfile}")
  # Strat Deployment
  puts "Deployment Started.",@test_status_log
  `ruby #{$deployfile}`
  rc=$?.exitstatus
  if rc == 0
  elsif rc == 254
    failure_handler "IP Assignment or Accessible"
  elsif rc == 253
    failure_handler "VM Deployment"
  elsif rc == 251
    failure_handler "IP range(Size: #{ip_pool.size}) specified doesn't have enough available IPs for #{$vm_num} of VMs"
  else
    failure_handler "Unknown"
  end

  #Post Deploy verification
  begin
    Timeout::timeout(300) do
      load $getipfile
    end
  rescue Timeout::Error => e
    failure_handler "IP Assignment"
  end
  vm_folder_moid = _get_folder_moid("#{$vm_prefix}-#{$cluster_name}-vms",_get_folder_moid($fd_name,""))
  actual_vm_num = `govc find -type m -i -dc "#{Shellwords.escape($dc_name)}" . -parent "#{vm_folder_moid}" -name "#{$vm_prefix}-*" | wc -l`.chomp.to_i
  #actual_vm_num = `rvc #{$vc_rvc} --path #{@folder_path_escape} -c "vsantest.perf.get_vm_count #{$vm_prefix}-*" -c 'exit' -q`.chomp.to_i
  if $vm_num != actual_vm_num #or (`rvc #{$vc_rvc} --path #{@folder_path_escape} -c "ls" -c 'exit' -q`.encode('UTF-8', :invalid => :replace).chomp =~ /no matches/)
    failure_handler "VM Deployment"
  end
  puts "Verifying If VMs are Accessible",@test_status_log

  vms = _ssh_to_vm
  for vm in vms
    vm.strip!
    if !ssh_valid(vm,'root','vdbench')
      puts "VM #{vm} is NOT Reachable through SSH",@test_status_log
      puts "Please Verify IP Address and SSH Policy in Client Network",@test_status_log
      failure_handler "VMs Accessibility Validation"
    end
  end
  File.delete($warmuptempfile) if File.exist?($warmuptempfile)
  puts "Deployment Successfully Finished.",@test_status_log
else
  puts "Existing VMs are Successfully Verified.",@test_status_log
end

load $getipfile
# Strat warm up if needed
if $warm_up_disk_before_testing != "NONE" and not File.exist?($warmuptempfile)
  puts "Virtual Disk Preparation #{$warm_up_disk_before_testing} Started.(May take half to couple of hours depending on the size of VMs deployed)",@test_status_log
  cmd=system("source #{$credentialconffile}; ruby #{$warmupfile} #{$warm_up_disk_before_testing}")
  if cmd
    puts "Virtual Disk Preparation Finished, Sleeping for 120 Seconds...",@test_status_log
    FileUtils.touch($warmuptempfile)
    sleep(120)
  else
    failure_handler "VMDK Wamrup"
  end
end

# Strat I/O test
puts "I/O Test Started.",@test_status_log
load $testfile
puts "I/O Test Finished.",@test_status_log

if $cleanup_vm
  puts "Cleaning Up Client VMs",@test_status_log
  load $cleanupinfolderfile
else
  system("rvc #{$vc_rvc} --path #{@folder_path_escape} -c 'mv temp/* .' -c 'destroy temp' -c 'exit' -q")
end

# Turn off static if enalbed
system("ifconfig -s eth1 0.0.0.0; ifconfig eth1 down; ifconfig eth1 up") if $static_enabled

# Set vSAN perf service back
if $vsan_debug
  @vsan_clusters.each do |vsan_cluster|
    if _is_ps_enabled(vsan_cluster) and @verbose_mode != "Enabled"
      puts "Disable vSAN Performance Service verbose mode in cluster #{vsan_cluster}", @test_status_log
      _set_perfsvc_verbose_mode(false,vsan_cluster)
    end
  end

  cmd = "esxcli vsan perf set --interval=300; echo $?" 
  $perfsvc_master_nodes.each do |master_node|
    host_key = $hosts_credential.has_key?(master_node) ? master_node : $hosts_credential.keys[0]   
    host_username = $hosts_credential[host_key]["host_username"]
    host_password = $hosts_credential[host_key]["host_password"]

    puts "Setting vSAN Performance Service interval to 300s on #{master_node}", @test_status_log
    if ssh_valid(master_node,host_username,host_password)
      if ssh_cmd(master_node,host_username,host_password,cmd).chomp == "0"
        puts "vSAN Performance Service interval is set back to 300s on Performance Service master node: #{master_node} ", @test_status_log
      else
        puts "Failed to set vSAN Performance Service interval back on Performance Service master node: #{master_node}", @test_status_log
      end
    end
  end
end

#Get XLS file
puts "Generating XLS file for this run...", @test_status_log

if $tool == "vdbench"
  ARGV = [$output_path_dir]
  load $getxlsvdbenchfile
else
  ARGV = [$output_path_dir]
  load $getxlsfiofile
end

# Done
puts "Testing Finished",@test_status_log