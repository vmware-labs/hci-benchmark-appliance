require 'yaml'
require 'fileutils'
require 'timeout'
require 'shellwords'
require 'find'
require_relative "util.rb"
require_relative "rvc-util.rb"

@vm_health_check_file = "#{$log_path}/vm-health-check.log"
@status_log = "#{$log_path}/test-status.log"
@folder_path_escape = _get_folder_path_escape[0]
@retry_time = 5
@multiwriter_disks_num = 0
@multiwriter_disks = []

class Numeric
  Alpha26 = ("a".."z").to_a
  def alph
    return "" if self < 1
    s, q = "", self
    loop do
      q, r = (q - 1).divmod(26)
      s.prepend(Alpha26[r])
      break if q.zero?
    end
    s
  end
end

def failure_handler(what_failed)
  puts "[ERROR] #{what_failed}",@vm_health_check_file
  puts "[ERROR] Existing VMs not Compatible",@vm_health_check_file
  puts "ABORT: VMs are not existing or Existing VMs are not Compatible",@vm_health_check_file
  exit(255)
end

puts "Checking Existing VMs...",@status_log
#Check vm folder
puts 'Verifying If Folder Exists...',@vm_health_check_file
vm_folder_moid = _get_folder_moid("#{$vm_prefix}-#{$cluster_name}-vms",_get_folder_moid($fd_name,""))
if vm_folder_moid == ""
  #if !system(%{rvc #{$vc_rvc} --path #{@folder_path_escape} -c 'exit' -q > /dev/null 2>&1})
  failure_handler "No VM Folder Found"
else
  puts 'Folder Verified...',@vm_health_check_file
end
puts "Moving all vms to the current folder",@vm_health_check_file
puts `rvc #{$vc_rvc} --path #{@folder_path_escape} -c "mv temp/* ." -c 'exit' -q`,@vm_health_check_file

#How many VMs actually in the folder
@actual_vm_num = `govc find -type m -i -dc "#{Shellwords.escape($dc_name)}" . -parent "#{vm_folder_moid}" -name "#{$vm_prefix}-*" | wc -l`.chomp.to_i
#@actual_vm_num = `rvc #{$vc_rvc} --path #{@folder_path_escape} -c "vsantest.perf.get_vm_count #{$vm_prefix}-*" -c 'exit' -q`.to_i

#Check Number of VMs
if ($vm_num > @actual_vm_num) #or `rvc #{$vc_rvc} --path #{@folder_path_escape} -c "ls" -c 'exit' -q`.encode('UTF-8', :invalid => :replace).chomp =~ /no matches/
  failure_handler "Not Enough VMs Deployed"
else
  puts "There are #{@actual_vm_num} VMs in the Folder, #{$vm_num} out of #{@actual_vm_num} will be used", @vm_health_check_file
end

#Check VMs' resource info
#vms_resource_map = eval(`rvc #{$vc_rvc} --path #{@folder_path_escape} -c "vsantest.perf.get_vm_resource_info #{$vm_prefix}-*" -c 'exit' -q`.encode('UTF-8', :invalid => :replace).chomp)
puts `rvc #{$vc_rvc} --path #{@folder_path_escape} -c 'mv temp/* .' -c 'mkdir temp' -c 'mv #{$vm_prefix}-* temp' -c 'exit' -q`, @vm_health_check_file
#puts "Existing VMs info\n#{vms_resource_map}", @vm_health_check_file
temp_folder_moid = _get_folder_moid("temp",vm_folder_moid)

@network_id = ""
if (_is_duplicated "nt", $network_name)[0]
  deploy_hosts_list = _get_deploy_hosts_list
  _get_moid("nt",$network_name).each do |net_obj|
    network_type = net_obj[0]
    network_ref = net_obj[1]
    network_id = network_type + ":" + network_ref
    nw_hosts_id_list = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{network_id} host`.chomp.split(",")
    deploy_hosts_list.each do |host|
      if nw_hosts_id_list.include? _get_moid("hs",host).join(":")
        @network_id = network_id
        break
      end
    end
  end
else
  @network_id = _get_moid("nt",$network_name).join(":")
end

vms_moid_to_use = []
$datastore_names.each do |datastore|
  good_vms_moid = `govc find -type m -i -dc "#{Shellwords.escape($dc_name)}" . \
  -parent "#{temp_folder_moid}" \
  -datastore #{_get_moid("ds",datastore).join(":")} \
  -config.hardware.numCPU #{$num_cpu} \
  -network #{@network_id} \
  -config.hardware.memoryMB #{$size_ram*1024}`.chomp.split("\n")
  if good_vms_moid.size >= $vms_perstore
    puts "There are #{good_vms_moid.size} can be used, will use #{$vms_perstore} for testing Datastore #{datastore}" ,@vm_health_check_file
  else
    failure_handler "Not enough proper VMs in #{datastore}"
  end

  good_vms_moid.each do |vm_moid|
    hash_arr = _save_str_to_hash_arr `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -json "#{vm_moid}" config.hardware.device`
    hash_arr.each do |hash_d|
      hash_d[0]["Val"]["VirtualDevice"].each do |dev|
        if dev["DeviceInfo"]["Label"].include? "Hard disk"
          if dev["Backing"]["Sharing"] == "sharingMultiWriter" #either sharingNone or sharingMultiWriter
            @multiwriter_disks_num += 1
            @multiwriter_disks << dev["Backing"]["FileName"] if not @multiwriter_disks.include? dev["Backing"]["FileName"]
          end
        end
      end
    end
  end
  if $multiwriter
    failure_handler "Found #{@multiwriter_disks.size} multi-writer disks in #{good_vms_moid.size} VMs, which is different from the configuration" if @multiwriter_disks.size != $number_data_disk or @multiwriter_disks_num != ($number_data_disk * $vm_num)
  else
    failure_handler "Found #{@multiwriter_disks_num} multi-writer disks, which is incompatible" if @multiwriter_disks_num > 0
  end

  good_vms_moid.each_with_index do |vm_moid,i|
    puts `govc object.mv -dc "#{Shellwords.escape($dc_name)}" #{vm_moid} "#{vm_folder_moid}"`,@vm_health_check_file
    vms_moid_to_use << vm_moid
    break if i == $vms_perstore - 1
  end
end

#Reboot all VMs
begin
  Timeout::timeout(720) do
    puts "Rebooting All the Client VMs...",@vm_health_check_file
    puts `echo #{vms_moid_to_use.join(" ")} | xargs govc vm.power -dc "#{Shellwords.escape($dc_name)}" -M -moid -r`,@vm_health_check_file
    #puts `echo #{vms_moid_to_use.join(" ")} | xargs govc vm.ip -v4 -dc "#{Shellwords.escape($dc_name)}" -moid -wait 120s`,@vm_health_check_file
    puts "All the Client VMs Rebooted, wait 120 seconds...",@vm_health_check_file
    sleep(120)
    puts "Getting all the Client VMs IP...",@vm_health_check_file
    load $getipfile
  end
rescue Timeout::Error => e
  failure_handler "IP Assignment Failed"
end

puts "Verifying all the Client VMs Disks...",@vm_health_check_file

def verifyVm(vm)
  single_vm_health_file = "#{$log_path}/#{vm}-health-check.log"
  puts "=======================================================",single_vm_health_file
  puts "Verifying VM #{vm}...",single_vm_health_file
  #Check VMDKs
  #Check # of VMDKs
  fail = false
  for i in 1..@retry_time
    if !ssh_valid(vm, 'root', 'vdbench')
      puts "VM #{vm} accessbility #{i}th try is failed, sleep for 10s...", single_vm_health_file
      fail = true
      sleep(10)
    else
      fail = false
      break
    end
  end

  failure_handler "VM #{vm} Not Accessible" if fail
  @num_disk_in_vm = ssh_cmd(vm,'root','vdbench','ls /sys/block/ | grep "sd" | wc -l').chomp.to_i - 1

  if @num_disk_in_vm < $number_data_disk
    failure_handler "Too Many Data Disk Specified"
  else
    puts "There are #{@num_disk_in_vm} Data Disks in VM #{vm}",single_vm_health_file
  end
  #Check size of VMDKs
  for vmdk_index in 1..$number_data_disk
    @data_disk_name = "sd" + vmdk_index.alph
    @sectors_per_vmdk = ssh_cmd(vm,'root','vdbench',"cat /sys/block/#{@data_disk_name}/size").to_i
    if @sectors_per_vmdk/(2*1024*1024) != $size_data_disk
      failure_handler "Data Disk Size Mis-match"
    else
      puts "The #{vmdk_index}/#{$number_data_disk} Data Disk size is #{$size_data_disk}GB", single_vm_health_file
    end
  end

  @test_vdbench_binary_cmd = "test -f /root/vdbench/vdbench && echo $?"
  @test_fio_binary_cmd = "test -f /root/fio/fio && echo $?"
  return_code = ssh_cmd(vm,'root','vdbench', @test_fio_binary_cmd)
  if return_code == ""
    puts "Fio binary does not exist, upload it to client VM #{vm}", single_vm_health_file
    fio_file = "#{$fio_source_path}/fio"
    scp_item(vm,'root','vdbench',fio_file,"/root/fio")
    return_code = ssh_cmd(vm,'root','vdbench', @test_fio_binary_cmd)
    if return_code == ""
      failure_handler "Can not find Fio binary"
    end
  end

  #TBD, can just call rvc to re-install
  #  install_scripts vms
  #  install_diskinit vms
  #Check graphite scripts
  #Check diskinit

  #Check vdbench binary
  if $tool == "vdbench"
    return_code = ssh_cmd(vm,'root','vdbench', @test_vdbench_binary_cmd)
    if return_code == ""
      puts "Vdbench binary does not exist, upload it to client VM #{vm}",single_vm_health_file
      ssh_cmd(vm,'root','vdbench','rm -rf /root/vdbench ; mkdir -p /root/vdbench')
      vdbench_file = Find.find($vdbench_source_path).select {|path| path if path =~ /^.*.zip$/}[0]
      scp_item(vm,'root','vdbench',vdbench_file,"/root/vdbench")
      ssh_cmd(vm,'root','vdbench','cd /root/vdbench ; unzip -q *.zip')

      return_code = ssh_cmd(vm,'root','vdbench',@test_vdbench_binary_cmd)
      if return_code == ""
        failure_handler "Can not find Vdbench binary"
      end
    end
  end
  puts "VM #{vm} Verified.", @vm_health_check_file
end

vms = _ssh_to_vm
tnode = []
vms.each do |s|
  s.strip!
  tnode << Thread.new{verifyVm(s)}
end
tnode.each{|t|t.join}

puts "DONE: VMs are healthy and could be reused for I/O testing",@vm_health_check_file
