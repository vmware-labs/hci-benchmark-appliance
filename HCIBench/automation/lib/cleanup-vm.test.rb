#!/usr/bin/ruby
require_relative "rvc-util.rb"
require_relative "util.rb"

@vm_cleanup_log = "#{$log_path}/vm-cleanup.log"
vm_folder_moid = _get_folder_moid("#{$vm_prefix}-#{$cluster_name}-vms",_get_folder_moid($fd_name,""))
begin
	tnode = []
	_get_hosts_list.each do |host|
		host_moid = _get_moid("hs",host).join(":")
		tnode << Thread.new{
puts `govc find -type m -i -dc "#{Shellwords.escape($dc_name)}" . -runtime.host "#{host_moid}" -name "#{$vm_prefix}-*" | xargs govc vm.power -dc "#{Shellwords.escape($dc_name)}" -off -moid`, @vm_cleanup_log
			puts `govc find -type m -i -dc "#{Shellwords.escape($dc_name)}" . -runtime.host "#{host_moid}" -name "#{$vm_prefix}-*" | xargs govc object.destroy -dc "#{Shellwords.escape($dc_name)}" `, @vm_cleanup_log
		}
	end
	tnode.each{|t|t.join}
	puts `govc object.destroy -dc "#{Shellwords.escape($dc_name)}" "#{vm_folder_moid}" 2>/dev/null`,@vm_cleanup_log
rescue Exception => e
	puts "dont worry, nothing critical",@vm_cleanup_log
	puts "#{e.class}: #{e.message}",@vm_cleanup_log
end
