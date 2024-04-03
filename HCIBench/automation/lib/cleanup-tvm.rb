#!/usr/bin/ruby
require_relative "rvc-util.rb"
require_relative "util.rb"

@tvm_cleanup_log = "#{$log_path}/prevalidation/tvm-cleanup.log"
tvm_folder_moid = _get_folder_moid("#{$tvm_prefix}-#{$cluster_name}-vms", _get_folder_moid($fd_name,""))
begin
	tnode = []
	_get_hosts_list.each do |host|
		host_moid = _get_moid("hs",host).join(":")
		tnode << Thread.new{
			puts `govc find -type m -i -dc "#{Shellwords.escape($dc_name)}" . -runtime.host "#{host_moid}" -name "#{$tvm_prefix}-*" | xargs govc vm.destroy -dc "#{Shellwords.escape($dc_name)}" -m`, @tvm_cleanup_log
		}
	end
	tnode.each{|t|t.join}
	puts `govc object.destroy -dc "#{Shellwords.escape($dc_name)}" "#{tvm_folder_moid}" 2>/dev/null`,@tvm_cleanup_log
rescue Exception => e
	puts "dont worry, nothing critical"
	puts "#{e.class}: #{e.message}"
end
