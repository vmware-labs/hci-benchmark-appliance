#!/usr/bin/ruby
require 'timeout'
require_relative "rvc-util.rb"

@folder_path_escape = _get_folder_path_escape[0]
#vm_folder_moid = _get_folder_moid("#{$vm_prefix}-#{$cluster_name}-vms",_get_folder_moid($fd_name,""))
@reboot_log = "#{$log_path}/reboot.log"

begin
  Timeout::timeout(300) do
  	 #puts `govc find -type m -i -dc "#{Shellwords.escape($dc_name)}" . -parent "#{vm_folder_moid}" | xargs govc vm.power -dc "#{Shellwords.escape($dc_name)}" -r -moid -M`, @reboot_log
  	 #puts `govc find -type m -i -dc "#{Shellwords.escape($dc_name)}" . -parent "#{vm_folder_moid}" | xargs govc vm.ip -dc "#{Shellwords.escape($dc_name)}" -moid`, @reboot_log
	 puts `rvc #{$vc_rvc} --path #{@folder_path_escape} -c "vm.reboot_guest #{$vm_prefix}-*" -c "vm.ip #{$vm_prefix}-*" -c 'exit' -q`, @reboot_log
  end
rescue Timeout::Error => e
  puts "Client VMs failed to get IPs", @reboot_log
end
