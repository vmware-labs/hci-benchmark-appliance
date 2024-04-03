require 'shellwords'
require_relative "rvc-util.rb"
require_relative "util.rb"

def getVsanInfo(path)
  host_num = _get_hosts_list.count
  policy_rule_map = {}

  vsan_datastores = _get_vsandatastore_in_cluster
  if vsan_datastores == {}
    print "vSAN is not enabled!\n"
    return
  else
    vsan_datastore_names = vsan_datastores.keys & $datastore_names
    if vsan_datastore_names.empty?
      print "Not Testing on vSAN!"
      return
    end
    file = File.open("#{path}/vsan.cfg", 'w')
    vsan_datastore_names.each do |vsan_datastore_name|

      cluster_to_pick = $cluster_name
      if not _is_ds_local_to_cluster(vsan_datastore_name)
        @local = "Remote"
        cluster_to_pick = _get_vsan_cluster_from_datastore(vsan_datastore_name)
      else
        @local = "Local"
      end
      host_num = _get_hosts_list(cluster_to_pick).count
      vsan_stats_hash = _get_vsan_disk_stats(cluster_to_pick)
      policy_name, rules = _get_vsan_default_policy(vsan_datastore_name)
      rules = _get_storage_policy_rules($storage_policy) if $storage_policy and not $storage_policy.empty? and not $storage_policy.strip.empty?
      policy_rule_map = _get_policy_rule_map(rules)

      policy_ftm = "RAID-1(Mirroring)-Performance"
      policy_ftm = policy_rule_map["VSAN.replicaPreference.replicaPreference"].split(" ")[-1] if policy_rule_map.key?("VSAN.replicaPreference.replicaPreference")
      policy_pftt = policy_rule_map["VSAN.hostFailuresToTolerate.hostFailuresToTolerate"] || "1"
      policy_sftt = policy_rule_map["VSAN.subFailuresToTolerate.subFailuresToTolerate"] || "0"
      policy_csc = policy_rule_map["VSAN.checksumDisabled.checksumDisabled"] || "false"

      policy_compression_svc = ""
      #policy_encryption_svc = ""

      #vsan2: no pref==!has_key?("VSAN.dataService.dataEncryption")==$cluster_setting, since policy can override cluster setting, this param is useless
      #if policy_rule_map.has_key?("VSAN.dataService.dataEncryption")
      #  policy_encryption_svc = policy_rule_map["VSAN.dataService.dataEncryption"].split(" ")[-1]
      #end

      #vsan2: no pref==!has_key("VSAN.dataService.spaceEfficiency")==comp-only only; no dd/c; dd/c; comp-only
      #vsan1: no pref==!has_key("VSAN.dataService.spaceEfficiency")==$cluster_setting;
      if policy_rule_map.has_key?("VSAN.dataService.spaceEfficiency")
        policy_compression_svc = policy_rule_map["VSAN.dataService.spaceEfficiency"].split(" ")[-1]
      elsif $vsan_version == 2
        policy_compression_svc = "Compression Only"
      end

      if not _is_ds_local_to_cluster(vsan_datastore_name)
        @local = "Remote"
        cluster_to_pick = _get_vsan_cluster_from_datastore(vsan_datastore_name)
      else
        @local = "Local"
      end
      total_cache_size = vsan_stats_hash["Total_Cache_Size"]
      num_of_dg = vsan_stats_hash["Total number of Disk Groups"]
      num_of_cap = vsan_stats_hash["Total number of Capacity Drives"]
      dedup = vsan_stats_hash["Dedupe Scope"]
      vsan_type = vsan_stats_hash["vSAN type"]
      in_transit_encryption = vsan_stats_hash["Data in-Transit Encryption"]
      at_rest_encryption = vsan_stats_hash["Data at-Rest Encryption"]

      if num_of_dg != 0 #for traditional vSAN

        if vsan_type == "All-Flash"
          total_cache_size = [num_of_dg * 600,total_cache_size].min
        end
        num_dg_p_host = num_of_dg/host_num
        cap_per_dg = num_of_cap/host_num/num_dg_p_host

        file.puts "#{@local} vSAN Datastore Name: #{vsan_datastore_name}\n"
        file.puts "vSAN ESA Enabled: False\n"
        file.puts "vSAN Type: #{vsan_type}\n"
        file.puts "Number of Hosts: #{host_num}\n"
        file.puts "Disk Groups per Host: #{num_dg_p_host}\n"
        #file.puts "Cache model: 1 \n"
        file.puts "Total Cache Disk Size: #{total_cache_size} GB"
        file.puts "Capacity Disk per Disk Group: #{cap_per_dg}\n"
        se = "Deduplication/Compression"
        if dedup == 1
          se = "Compression Only"
        elsif dedup == 0
          se = "None"
        end
        file.puts "Space Efficiency: #{se}\n"
        file.puts "Data At-Rest Encryption: #{at_rest_encryption}\n"
        file.puts "Data In-Transit Encryption: #{in_transit_encryption}\n"
        file.puts "Fault Tolerance Preference: #{policy_ftm}\n"
        file.puts "Host Primary Fault Tolerance: #{policy_pftt}\n"
        file.puts "Host Secondary Fault Tolerance: #{policy_sftt}\n"
        file.puts "Checksum Disabled: #{policy_csc.capitalize}\n"
        #sum_stats_full[0].each do |stat|
        #  file.puts stat
        #end
        file.puts vsan_datastores[vsan_datastore_name].transform_keys(&:capitalize).transform_values{|v| if v.instance_of? String; v + " GB" ;else v.to_s.capitalize ;end}.to_yaml
        file.puts "============================================="
      else # for vSAN MAX

        file.puts "#{@local} vSAN Datastore Name: #{vsan_datastore_name}\n"
        file.puts "vSAN ESA Enabled: True\n"
        file.puts "vSAN Type: Single Tier Storage Pool\n"
        file.puts "Number of Hosts: #{host_num}\n"
        file.puts "Number of Disks in the Storage Pool: #{num_of_cap}\n"
        file.puts "Space Efficiency: #{policy_compression_svc}\n"
        file.puts "Data At-Rest Encryption: #{at_rest_encryption}\n"
        file.puts "Data In-Transit Encrption: #{in_transit_encryption}\n"
        file.puts "Fault Tolerance Preference: #{policy_ftm}\n"
        file.puts "Host Primary Fault Tolerance: #{policy_pftt}\n"
        file.puts "Host Secondary Fault Tolerance: #{policy_sftt}\n"
        file.puts "Checksum Disabled: #{policy_csc.capitalize}\n"
        #sum_stats_full[0].each do |stat|
        #  file.puts stat
        #end
        file.puts vsan_datastores[vsan_datastore_name].transform_keys(&:capitalize).transform_values{|v| if v.instance_of? String; v + " GB" ;else v.to_s.capitalize ;end}.to_yaml
        file.puts "============================================="
      end
      health_file = File.open("#{path}/#{cluster_to_pick}-health.info", 'w')
      health_file.puts _get_vsan_health_summary(cluster_to_pick)
    end
    file.puts "Cluster Hosts Map\n"
    file.puts _get_cluster_hosts_map.to_yaml
    file.close()
  end
end

getVsanInfo(ARGV[0]) if ARGV[0]
