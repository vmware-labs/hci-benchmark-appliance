require_relative 'rvc-util.rb'
require_relative 'util.rb'
p _get_resource_used_by_guest_vms("w1-pe-vsan-esx-014.eng.vmware.com")
p _get_host_spare_compute_resource("w1-pe-vsan-esx-014.eng.vmware.com")
exit
p _get_num_of_vm_to_deploy
p _get_cluster_hosts_map
p _get_storage_policy_rules("test")
p _get_compliant_datastore_ids_escape()
p _get_vsandatastore_in_cluster
p _get_moid "cl","vSAN2"

$datastore_names.each do |ds|
p ds
  p _get_vsan_cluster_from_datastore(ds)
  p _get_ds_id_by_name(ds)
  p _is_vsan(ds)
  p _get_hosts_list_by_ds_name(ds)
  p _get_vsan_default_policy(ds)
end

p _get_deploy_hosts_list
