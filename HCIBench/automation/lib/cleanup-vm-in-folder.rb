#!/usr/bin/ruby
require_relative "rvc-util.rb"
require_relative "util.rb"

@vm_cleanup_log = "#{$log_path}/vm-cleanup.log"
vm_folder_moid = _get_folder_moid("#{$vm_prefix}-#{$cluster_name}-vms",_get_folder_moid($fd_name,""))
begin
	puts `govc find -type m -i -dc "#{Shellwords.escape($dc_name)}" . -parent "#{vm_folder_moid}" | xargs govc vm.destroy -dc "#{Shellwords.escape($dc_name)}" -m`, @vm_cleanup_log
	puts `govc object.destroy -dc "#{Shellwords.escape($dc_name)}" "#{vm_folder_moid}" 2>/dev/null`,@vm_cleanup_log
rescue Exception => e
	puts "dont worry, nothing critical",@vm_cleanup_log
	puts "#{e.class}: #{e.message}",@vm_cleanup_log
end
