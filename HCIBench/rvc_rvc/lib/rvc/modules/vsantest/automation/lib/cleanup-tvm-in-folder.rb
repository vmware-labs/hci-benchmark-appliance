#!/usr/bin/ruby
require_relative "rvc-util.rb"
require_relative "util.rb"

@tvm_cleanup_log = "#{$log_path}/prevalidation/tvm-cleanup.log"
tvm_folder_moid = _get_folder_moid("#{$tvm_prefix}-#{$cluster_name}-vms",_get_folder_moid($fd_name,""))
begin
	puts `govc find -type m -i -dc "#{Shellwords.escape($dc_name)}" . -parent "#{tvm_folder_moid}" | xargs govc vm.destroy -dc "#{Shellwords.escape($dc_name)}" -m`, @tvm_cleanup_log
	puts `govc object.destroy -dc "#{Shellwords.escape($dc_name)}" "#{tvm_folder_moid}" 2>/dev/null`,@tvm_cleanup_log
rescue Exception => e
	puts "dont worry, nothing critical",@tvm_cleanup_log
	puts "#{e.class}: #{e.message}",@tvm_cleanup_log
end
