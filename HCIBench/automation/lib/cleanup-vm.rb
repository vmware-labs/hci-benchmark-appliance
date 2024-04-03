#!/usr/bin/ruby
require_relative "rvc-util.rb"
require_relative "util.rb"

@vm_cleanup_log = "#{$log_path}/vm-cleanup.log"
@folder_path_escape, @folder_path_escape_gsub = _get_folder_path_escape

def createVmFolder
  _get_cl_path
  move_vms_action_escape = Shellwords.escape(%{mv hosts/*/vms/#{$vm_prefix}-* #{@folder_path_escape}})
  puts `rvc #{$vc_rvc} -c "mkdir #{@folder_path_escape_gsub}" -c 'exit' -q`, @vm_cleanup_log
  puts `rvc #{$vc_rvc} --path #{$cl_path_escape} -c #{move_vms_action_escape} -c 'exit' -q`, @vm_cleanup_log
end

if $multiwriter
	createVmFolder
end

vm_folder_moid = _get_folder_moid("#{$vm_prefix}-#{$cluster_name}-vms",_get_folder_moid($fd_name,""))

begin
	tnode = []
	_get_hosts_list.each do |host|
		host_moid = _get_moid("hs",host).join(":")
		tnode << Thread.new{
		if $multiwriter
			puts `govc find -type m -i -dc "#{Shellwords.escape($dc_name)}" . -runtime.host "#{host_moid}" -name "#{$vm_prefix}-*" | xargs govc vm.power -dc "#{Shellwords.escape($dc_name)}" -off -moid`, @vm_cleanup_log
		else	
			puts `govc find -type m -i -dc "#{Shellwords.escape($dc_name)}" . -runtime.host "#{host_moid}" -name "#{$vm_prefix}-*" | xargs govc vm.destroy -dc "#{Shellwords.escape($dc_name)}" -m`, @vm_cleanup_log
		end
		}
	end
	tnode.each{|t|t.join}
	#puts `govc object.destroy -dc "#{Shellwords.escape($dc_name)}" "#{vm_folder_moid}" 2>/dev/null`,@vm_cleanup_log
rescue Exception => e
	puts "dont worry, nothing critical",@vm_cleanup_log
	puts "#{e.class}: #{e.message}",@vm_cleanup_log
ensure
	puts `govc object.destroy -dc "#{Shellwords.escape($dc_name)}" "#{vm_folder_moid}" 2>/dev/null`,@vm_cleanup_log
end
