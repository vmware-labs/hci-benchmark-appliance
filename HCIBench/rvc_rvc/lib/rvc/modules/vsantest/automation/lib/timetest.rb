require 'benchmark'
require 'yaml'
load '/opt/automation/lib/rvc-util.rb'
method_arr = ["_get_dc_path",
	"_get_cl_path(cluster_name)", 
	"_get_folder_path_escape", 
	"_get_tvm_folder_path_escape", 
	"_get_hosts_list", 
	"_get_deploy_hosts_list", 
	"_get_hosts_list_in_ip", 
	"_get_hosts_list_by_ds_name(datastore_name)", 
	"_get_hosts_list_by_ds_name_in_ip(datastore_name)", 
	"_ssh_to_vm",
	"_get_ds_path_escape(datastore_name)", 
	"_is_vsan(datastore_name)",
	"_is_vsan_enabled",
	"_is_ps_enabled(cluster_name)",
	"_get_vsandatastore_in_cluster",
	"_get_ip_addr",
	"_is_ip(ip)",
	"_get_ip_from_hostname(hostname)",
	"_get_perfsvc_master_node(cluster_name)",
	"_set_perfsvc_verbose_mode(verbose_mode,cluster_name)",
	"_get_ip_pools",
	"_range_big_enough",
	"_get_num_of_tvm_to_deploy",
	"_get_num_of_vm_to_deploy",
	"_pick_vsan_cluster_for_easy_run", 
	"_is_ds_local_to_cluster(datastore_name)", 
	"_get_vsan_cluster_from_datastore(datastore_name)", 
	"_get_compliant_datastore_ids_escape(storage_policy)", 
	"_get_ds_id_by_name(datastore_name)", 
	"_get_all_vsan_lsom_clusters", 
	"_get_all_vsan_clusters", 
	"_get_vsan_default_policy(datastore_name)",
	"_get_storage_policy_rules(storage_policy)",
	"_get_vsan_disk_stats(cluster_name)",
	"_get_vsan_type(cluster_name)",
	"_get_cluster_hosts_map",
	"_get_host_spare_compute_resource(host)",
	"_get_datastore_capacity_and_free_space(datastore_name)",
	"_get_cpu_usage(test_case_path)",
	"_get_ram_usage(test_case_path)",
	"_get_vsan_cpu_usage(test_case_path))"]

method_arr.each do |function|
	parameters = []
	function_name = ""
	if function.include? "("
		function_name = function.split("(")[0]
		function.split("(")[1].split(")")[0].split(",").each do |param|
			value = nil
			case param
			when "datastore_name"
				value = "vsanDatastore-2"
			when "verbose_mode"
				value = false
			when "test_case_path"
				value = "/opt/output/results/easy-run-1602614490/vdb-8vmdk-100ws-4k-70rdpct-100randompct-4threads-1602617371"
			when "ip"
				value = "aabvc"
			when "cluster_name"
				value = "vSAN1"
			when "hostname"
				value = "w1-pe-vsan-esx-006.eng.vmware.com"
			when "storage_policy"
				value = "vSAN Default Storage Policy"
			end
			parameters << instance_variable_set("@#{param}", value)
		end

	end
	
	if parameters == []
		print "#{function}: " + Benchmark.measure { send(function) }.total.to_s + "\n"
	else
		print "#{function_name}: " + Benchmark.measure { send(function_name,parameters.join(",")) }.total.to_s + "\n"
	end
end


method_arr = ["_get_dc_path",
	"_get_cl_path", 
	"_get_folder_path_escape", 
	"_get_tvm_folder_path_escape", 
	"_get_hosts_list", 
	"_get_deploy_hosts_list", 
	"_get_hosts_list_in_ip", 
	"_get_hosts_list_by_ds_name", 
	"_get_hosts_list_by_ds_name_in_ip", 
	"_ssh_to_vm",
	"_get_ds_path_escape", 
	"_is_vsan",
	"_is_vsan_enabled",
	"_is_ps_enabled",
	"_get_vsandatastore_in_cluster",
	"_get_ip_addr",
	"_is_ip",
	"_get_ip_from_hostname",
	"_get_perfsvc_master_node",
	"_set_perfsvc_verbose_mode",
	"_get_ip_pools", 
	"_range_big_enough", 
	"_get_num_of_tvm_to_deploy",
	"_get_num_of_vm_to_deploy", 
	"_pick_vsan_cluster_for_easy_run", 
	"_is_ds_local_to_cluster", 
	"_get_vsan_cluster_from_datastore", 
	"_get_compliant_datastore_ids_escape", 
	"_get_ds_id_by_name", 
	"_get_all_vsan_lsom_clusters", 
	"_get_all_vsan_clusters", 
	"_get_vsan_default_policy",
	"_get_storage_policy_rules",
	"_get_vsan_disk_stats",
	"_get_vsan_type",
	"_get_cluster_hosts_map",
	"_get_host_spare_compute_resource",
	"_get_datastore_capacity_and_free_space",
	"_get_cpu_usage",
	"_get_ram_usage",
	"_get_vsan_cpu_usage"]

invoke_map = {}
fun_calls = {}

files = `ls /opt/automation/lib/*.rb | grep -v Usage.rb | grep -v timetest`.chomp.split("\n")
files.each do |filename|
	invoke_map[filename] = {}
	method_arr.each do |fun|
		fun_call = `grep #{fun} #{filename} | wc -l`.chomp.to_i
		if fun_call > 0
			if fun_calls[fun]
				fun_calls[fun] += fun_call
			else
				fun_calls[fun] = fun_call
			end
			if invoke_map[filename][fun]
				invoke_map[filename][fun] += fun_call
			else
				invoke_map[filename][fun] = fun_call
			end
		end
	end
	if invoke_map[filename] == {}
		invoke_map.delete(filename)
	end
end

puts invoke_map.to_yaml
puts fun_calls.to_yaml

