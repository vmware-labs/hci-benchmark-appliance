require 'nokogiri'
require 'active_support/all'
require 'yaml'
require "ipaddress"
require 'fileutils'
require 'resolv'
require "json"
require 'shellwords'
require 'ipaddr'
require "cgi"
require 'open3'
require "readline"
require_relative 'ossl_wrapper'
require_relative 'util.rb'

# Load the OSSL configuration file
ossl_conf = '../conf/ossl-conf.yaml'

$basedir=File.dirname(__FILE__)
entry = YAML.load_file("#$basedir/../conf/perf-conf.yaml")
#=====================2.8.1 bugs fix=======================
entry.each { |item,value| entry[item] = nil if value == ""}
entry["hosts"] = nil if entry["hosts"] == [""]
#==========================================================
#Param Def
$ip_prefix = entry["static_ip_prefix"]
$ip_Address = `ip a show dev eth0 | grep global | awk {'print $2'} | cut -d "/" -f1`.chomp
$docker_ip = `ip a show dev docker0 | grep global | awk {'print $2'} | cut -d "/" -f1`.chomp
$vc_ip = entry["vc"]

begin
  Gem.load_yaml
  osc = YAML.load_file(File.join($basedir, ossl_conf)).each_with_object({}) { |(k, v), m| m[k.to_sym] = v }
rescue Errno::ENOENT
  STDERR.puts "Could not open ossl configuration file: #{ossl_conf} error: file does not exist"
  exit(1)
rescue StandardError => e
  STDERR.puts "Culd not open ossl configuration file: #{ossl_conf} error: #{e}"
  exit(1)
end

vcp = entry["vc_password"]
if vcp
  begin
    osw = OSSLWrapper.new(osc)
    $vc_password = vcp.nil? || vcp.empty? ? '' : osw.decrypt(vcp)
  rescue StandardError => e
    STDERR.puts "Could not decrypt vCenter Password: Please re-save the vCenter Password.\nError: #{e}"
    exit(1)
  end
else
  $vcp_password = ''
end

$clear_cache = entry["clear_cache"]
$vsan_debug = entry["vsan_debug"]

$hosts_credential = entry["hosts_credential"]

$hosts_credential.keys.each do |host|
  host_val = $hosts_credential[host]
  if $clear_cache or $vsan_debug
    hp = host_val["host_password"]
    if hp
      begin
        osw = OSSLWrapper.new(osc)
        host_val["host_password"] = hp.nil? || hp.empty? ? '' : osw.decrypt(hp)
      rescue StandardError => e
        STDERR.puts "Could not open decrypt Host Password: Please re-save the Host #{host_val["host_name"]} Password.\nError: #{e}"
        exit(1)
      end
    else
      host_val["host_password"] = ''
    end
  end
end

$vc_username = entry["vc_username"]
$easy_run = entry["easy_run"]
$dc_name = entry["datacenter_name"].gsub("%","%25").gsub("/","%2f").gsub("\\","%5c")
$cluster_name = entry["cluster_name"].gsub("%","%25").gsub("/","%2f").gsub("\\","%5c")
$storage_policy = (entry["storage_policy"] || "").gsub('\\', '\\\\\\').gsub('"', '\"')
$resource_pool_name = (entry["resource_pool_name"] || "" ).gsub("%","%25").gsub("/","%2f").gsub("\\","%5c")
$resource_pool_name_escape = Shellwords.escape((entry["resource_pool_name"] || "" ).gsub("%","%25").gsub("/","%2f").gsub("\\","%5c"))
$fd_name = entry["vm_folder_name"] || ""
$vm_folder_name = Shellwords.escape(entry["vm_folder_name"] || "")
$network_name = (entry["network_name"] || "VM Network").gsub("%","%25").gsub("/","%2f").gsub("\\","%5c")
$datastore_names = entry["datastore_name"].map!{|ds|ds.gsub("%","%25").gsub("/","%2f").gsub("\\","%5c")}
$deploy_on_hosts = entry["deploy_on_hosts"]
$tool = entry["tool"]
$vm_prefix = entry["vm_prefix"] || $tool
$tvm_prefix = "hci-tvm"
$folder_name = "#{$vm_prefix}-#{$cluster_name}-vms".gsub("%","%25").gsub("/","%2f").gsub("\\","%5c")
$tvm_folder_name = "#{$tvm_prefix}-#{$cluster_name}-vms".gsub("%","%25").gsub("/","%2f").gsub("\\","%5c")
$all_hosts = entry["hosts"]
#$host_username = entry["host_username"]
$vm_num = entry["number_vm"]
$tvm_num = 0
$num_cpu = entry["number_cpu"] || 4
$size_ram = entry["size_ram"] || 8
$number_data_disk = entry["number_data_disk"]
$size_data_disk = entry["size_data_disk"]
$self_defined_param_file_path = entry["self_defined_param_file_path"]
$warm_up_disk_before_testing = entry["warm_up_disk_before_testing"]
$testing_duration = entry["testing_duration"] == "" ? nil : entry["testing_duration"]
$static_enabled = entry["static_enabled"]
$output_path = entry["output_path"]
$output_path_dir = "/opt/output/results/" + $output_path
$reuse_vm = entry["reuse_vm"]
$cleanup_vm = entry["cleanup_vm"]
$workloads = entry["workloads"] || ["4k70r"]
$latency_target = entry["latency_target"] || "Max"
$multiwriter = entry["multi_writer"] || false
#File path def
$allinonetestingfile = "#{$basedir}/all-in-one-testing.rb"
$cleanupfile = "#{$basedir}/cleanup-vm.rb"
$cleanuptvmfile = "#{$basedir}/cleanup-tvm.rb"
$cleanupinfolderfile = "#{$basedir}/cleanup-vm-in-folder.rb"
$credentialconffile = "#{$basedir}/../conf/credential.conf"
$deployfile = "#{$basedir}/deploy-vms.rb"
$deploytvmfile = "#{$basedir}/deploy-tvm.rb"
$dropcachefile = "#{$basedir}/drop-cache.rb"
$easyrunfile = "#{$basedir}/easy-run.rb"
$getipfile = "#{$basedir}/get-vm-ip.rb"
$gettvmipfile = "#{$basedir}/get-tvm-ip.rb"
$getxlsvdbenchfile = "#{$basedir}/get-xls-vdbench.rb"
$getxlsfiofile = "#{$basedir}/get-xls-fio.rb"
$getcpuusagefile = "#{$basedir}/getCpuUsage.rb"
$getramusagefile = "#{$basedir}/getRamUsage.rb"
$getvsancpuusagefile = "#{$basedir}/getPCpuUsage.rb"
$healthfile = "#{$basedir}/vm-health-check.rb"
$testfile = "#{$basedir}/io-test.rb"
$vmlistfile = "#{$basedir}/../tmp/vm.yaml"
$tvmlistfile = "#{$basedir}/../tmp/tvm.yaml"
$warmupfile = "#{$basedir}/disk-warm-up.rb"
$warmuptempfile = "#{$basedir}/../tmp/warmedup.tmp"
$parsefiofile = "#{$basedir}/parseFioResult.rb"
$parsevdbfile = "#{$basedir}/parseVdbResult.rb"
$generatereport = "#{$basedir}/generate_report.rb"
$getvsaninfo = "#{$basedir}/get-vsan-info.rb"
$humbug_link_file = "#{$basedir}/../tmp/humbug_link"
$resource_json_file_name = "resource_usage.info" 
$vsan_cpu_usage_file = "#{$basedir}/../tmp/vsan_cpu_usage_pct.info"
#Dir path def
$tmp_path = "#{$basedir}/../tmp/"
$log_path = "#{$basedir}/../logs/"
$vdbench_source_path = "/opt/output/vdbench-source"
$fio_source_path = "/opt/output/fio-source"
$compute_only_cluster = "" 
$total_datastore = $datastore_names.count
if IPAddress.valid? $vc_ip and IPAddress.valid_ipv6? $vc_ip
  $vc_rvc = Shellwords.escape("#{$vc_username}:#{$vc_password}") + "@[#{$vc_ip}]" + " -a"
else
  $vc_rvc = Shellwords.escape("#{$vc_username}:#{$vc_password}") + "@#{$vc_ip}" + " -a"
end
$occupied_ips = []
ENV['GOVC_USERNAME'] = "#{$vc_username}"
ENV['GOVC_PASSWORD'] = "#{$vc_password}"
if IPAddress.valid? $vc_ip and IPAddress.valid_ipv6? $vc_ip
  ENV['GOVC_URL'] = "[#{$vc_ip}]"
else
  ENV['GOVC_URL'] = "#{$vc_ip}"
end
ENV['GOVC_INSECURE'] = "true"
ENV['GOVC_DATACENTER'] = "#{$dc_name}"
ENV['GOVC_PERSIST_SESSION'] = "true"
$vm_num = 0 unless $vm_num
$vms_perstore = $vm_num / $total_datastore

$eth1_ip = ""
$vm_yaml_file = "#{$basedir}/../tmp/vm.yaml"
if $static_enabled and $ip_prefix.include? "Customize"
  $starting_static_ip = $ip_prefix.split(" ")[1].split("/")[0]
  $static_ip_size = $ip_prefix.split(" ")[1].split("/")[1]
elsif $static_enabled
  $starting_static_ip = $ip_prefix + ".0.1"
  $static_ip_size = "18"
end

$dc_path = ""
$cl_path = ""
$ip_pool = []
$vsan_perf_diag = false
$vsan_version = 1
$cluster_hosts_map = {}
$all_vsan_clusters = []
$all_vsan_lsom_clusters = []
$vsandatastore_in_cluster = {}
$hosts_deploy_list = []
$easy_run_vsan_cluster = ""
#clusters will be running grafana, should be called when cluster has ps enabled and against vsan datastore, if this will be used, local should always be the case
$telegraf_target_clusters_map = {}
#clusters will be running observer, should be called all the time to the local, along with remote vsan ds specified
$observer_target_clusters_arr = [$cluster_name]
$perfsvc_master_nodes = []
$vsan_debug_sharing_path = ""
$share_folder_name = "vsan_debug"
class MyJSON
  def self.valid?(value)
    result = JSON.parse(value)
    result.is_a?(Hash) || result.is_a?(Array)
  rescue JSON::ParserError, TypeError
    false
  end
end

def _save_str_to_hash_arr obj_str
  json_temp = ""
  hash_arr = []
  obj_str.each_line do |line|
    json_temp += line
    if MyJSON.valid?(json_temp)
      hash_arr << JSON.parse(json_temp)
      json_temp = ""
    end
  end
  return hash_arr
end

def _is_duplicated object_type, object_name
  object_name_escaped = Shellwords.escape(object_name)
  types = {"dc" => "d", "rp" => "p", "ds" => "s", "nt" => "n", "fd" => "f", "cl" => "c", "hs" => "h"}
  stdout, stderr, status = Open3.capture3(%{govc find -dc "#{Shellwords.escape($dc_name)}" -type #{types[object_type]} -name "#{object_name_escaped}"})
  if stderr != ""  
    return true, stderr
  elsif stdout.chomp.split("\n").size != 1 #_save_str_to_hash_arr(stdout).size != 1
    return true, "Found #{stdout.chomp.split("\n").size} #{object_name}"
  else
    return false,""
  end
end

def _has_resource object_type, object_name
  object_name_escaped = Shellwords.escape(object_name)
  types = {"dc" => "d", "rp" => "p", "ds" => "s", "nt" => "n", "fd" => "f", "cl" => "c", "hs" => "h"}
  return (`govc find -type #{types[object_type]} -dc "#{Shellwords.escape($dc_name)}" -name "#{object_name_escaped}"`.chomp != "")
end

def _get_folder_moid(folder_name, parent_moid = "")
  return "" if folder_name == ""
  folder_name_escaped = Shellwords.escape(folder_name)
  if parent_moid == ""
    parent_moid = `govc find -type f -i -dc "#{Shellwords.escape($dc_name)}" . -parent "#{_get_moid('dc',$dc_name).join(':')}" -name "vm"`.chomp
  end
  return `govc find -type f -i -dc "#{Shellwords.escape($dc_name)}" . -parent "#{parent_moid}" -name "#{folder_name_escaped}"`.chomp
=begin
  parent_moid = ""
  if parent_name != "" #get parent fd's moid
    parent_moid = _get_moid("fd",parent_name).join(":")
  else
    parent_moid = `govc find -type f -i -dc "#{Shellwords.escape($dc_name)}" . -parent "#{_get_moid('dc',$dc_name).join(':')}" -name "vm"`.chomp
  end
  return `govc find -type f -i -dc "#{Shellwords.escape($dc_name)}" . -parent "#{parent_moid}" -name "#{folder_name_escaped}"`.chomp
=end
end

def _host_healthy host_moid
 connect = JSON.parse(`govc object.collect -json -dc "#{Shellwords.escape($dc_name)}" -s "HostSystem:#{host_moid}" runtime.connectionState`)
 maintainance = `govc object.collect -json -dc "#{Shellwords.escape($dc_name)}" -s "HostSystem:#{host_moid}" runtime.inMaintenanceMode`.chomp
 return (connect == "connected" and maintainance == "false") ? true : false
end

def _multi_json_string str
  return (str[0] == "{" and str[-1] == "}") ? true : false
end

def _parse_multi_json str
  json_arr = []
  count = 0
  in_json = false
  start_pos = 0
  str.each_char.with_index do |char,index|
    if char == "{"
      start_pos = index if not in_json 
      in_json = true
      count = count + 1
    end
    count = count - 1 if char == "}"
    if count == 0 and in_json
	json_arr.push(str[start_pos..index])
        in_json = false
    end
  end
  return json_arr
end

def _get_moid object_type, object_name
  object_name_escaped = Shellwords.escape(object_name)
  types = {"dc" => "d", "rp" => "p", "ds" => "s", "nt" => "n", "fd" => "f", "cl" => "c", "hs" => "h"}
  path = "./"
  path = "/" if object_type == "dc"
  return_value = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -json -type #{types[object_type]} #{path} -name "#{object_name_escaped}"`.chomp
  if not _is_duplicated(object_type, object_name)[0]
    obj_js = JSON.parse(return_value)
    obj_type = obj_js["obj"]["type"]
    obj_id = obj_js["obj"]["value"]
    return obj_type,obj_id
  elsif _multi_json_string(return_value)
    objs = []
    _parse_multi_json(return_value).each do |object|
      obj_js = JSON.parse(object)
      obj_type = obj_js["obj"]["type"]
      obj_id = obj_js["obj"]["value"]
      objs.push([obj_type,obj_id])
    end
    return objs
  else
    return "",""
  end
end

def _get_name object_type, object_moid
  return `govc object.collect -s #{object_type}:#{object_moid} name`.chomp
end

def _get_dc_path
  if $dc_path != ""
    return $dc_path, $dc_path_escape 
  else
    ENV['GOVC_DATACENTER'] = ""
    $dc_path = `govc find -type d -name "#{Shellwords.escape($dc_name)}"`.chomp
    $dc_path = $dc_path.encode('UTF-8', :invalid => :replace)[1..-1] if $dc_path != ""
    $dc_path_escape = Shellwords.escape("/#{$vc_ip}/#{$dc_path}")
  end
  ENV['GOVC_DATACENTER'] = "#{$dc_name}"
  return $dc_path, $dc_path_escape
end

def _get_cl_path(cluster_name = $cluster_name)
  return $cl_path, $cl_path_escape if (cluster_name == $cluster_name) and $cl_path != ""
  $dc_path, $dc_path_escape = _get_dc_path
  @computer_path_escape = Shellwords.escape("/#{$vc_ip}/#{$dc_path}/computers")
  cl_path = ""
  cl_arr = `rvc #{$vc_rvc} --path #{@computer_path_escape} -c 'find .' -c 'exit' -q`.encode('UTF-8', :invalid => :replace).split("\n")
  cl_arr.each do |cl|
    if cl[/#{Regexp.escape cluster_name}$/] and (cl.partition(' ').last == cluster_name or cl.split('/').last == cluster_name)
      cl_path = "computers/#{cl.partition(' ').last}"
    end
  end
  cl_path_escape = Shellwords.escape("/#{$vc_ip}/#{$dc_path}/#{cl_path}") if cl_path != ""
  if cluster_name == $cluster_name
    $cl_path = cl_path
    $cl_path_escape = cl_path_escape
  end
  return cl_path, cl_path_escape
end

def _get_folder_path_escape
  $dc_path, $dc_path_escape = _get_dc_path
  folder_path_escape = ""
  folder_path_escape_gsub = ""
  if $fd_name and $fd_name != ""
    folder_path_escape = Shellwords.escape("/#{$vc_ip}/#{$dc_path}/vms/#{$fd_name}/#{$vm_prefix}-#{$cluster_name}-vms")
    folder_path_escape_gsub = Shellwords.escape("/#{$vc_ip}/#{$dc_path.gsub('"','\"')}/vms/#{$fd_name.gsub('"','\"')}/#{$vm_prefix}-#{$cluster_name.gsub('"','\"')}-vms")
  else
    folder_path_escape = Shellwords.escape("/#{$vc_ip}/#{$dc_path}/vms/#{$vm_prefix}-#{$cluster_name}-vms")
    folder_path_escape_gsub = Shellwords.escape("/#{$vc_ip}/#{$dc_path.gsub('"','\"')}/vms/#{$vm_prefix}-#{$cluster_name.gsub('"','\"')}-vms")
  end
  return folder_path_escape, folder_path_escape_gsub
end

def _get_tvm_folder_path_escape
  $dc_path, $dc_path_escape = _get_dc_path
  tvm_folder_path_escape = ""
  tvm_folder_path_escape_gsub = ""
  if $fd_name and $fd_name != ""
    tvm_folder_path_escape = Shellwords.escape("/#{$vc_ip}/#{$dc_path}/vms/#{$fd_name}/#{$tvm_prefix}-#{$cluster_name}-vms")
    tvm_folder_path_escape_gsub = Shellwords.escape("/#{$vc_ip}/#{$dc_path.gsub('"','\"')}/vms/#{$fd_name.gsub('"','\"')}/#{$tvm_prefix}-#{$cluster_name.gsub('"','\"')}-vms")
  else
    tvm_folder_path_escape = Shellwords.escape("/#{$vc_ip}/#{$dc_path}/vms/#{$tvm_prefix}-#{$cluster_name}-vms")
    tvm_folder_path_escape_gsub = Shellwords.escape("/#{$vc_ip}/#{$dc_path.gsub('"','\"')}/vms/#{$tvm_prefix}-#{$cluster_name.gsub('"','\"')}-vms")
  end
  return tvm_folder_path_escape, tvm_folder_path_escape_gsub
end

#returning all [hosts] in the cluster
def _get_hosts_list(cluster_name = $cluster_name)
  hosts_list = []
  host_system_id_arr = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("cl",cluster_name).join(":")} host`.chomp.split(",")
  host_system_id_arr.each do |host_system_id|
    hosts_list << `govc object.collect -s #{host_system_id} name`.chomp
  end
  return hosts_list
end

#returning [host] for vm to deploy w/o ds restriction
def _get_deploy_hosts_list
  return $hosts_deploy_list if $hosts_deploy_list != []
  if $deploy_on_hosts
    $hosts_deploy_list = $all_hosts 
  else
    $hosts_deploy_list = _get_hosts_list
  end
  return $hosts_deploy_list #.reject{|x| not _host_healthy(_get_moid("hs",x)[1])}
end

def _get_hosts_list_in_ip(cluster_name = $cluster_name)
  hosts = _get_hosts_list(cluster_name)
  hosts.map!{|host| _get_ip_from_hostname(host)}
  return hosts
end

def _get_hosts_list_by_ds_name(datastore_name)
  hosts_list = []
  host_system_hash = JSON.parse(`govc object.collect -json -s #{_get_moid("ds",datastore_name).join(":")} host`.chomp)
  host_system_hash.each do |host_system|
    if host_system["mountInfo"]["accessible"]
      obj_type = host_system["key"]["type"]
      obj_id = host_system["key"]["value"]
      if _host_healthy(obj_id)
        hosts_list << _get_name(obj_type, obj_id) 
      end
    end
  end
  return hosts_list
end

def _get_hosts_list_by_ds_name_in_ip(datastore_name)
  hosts_list = _get_hosts_list_by_ds_name(datastore_name)
  hosts_list.map!{|host| _get_ip_from_hostname(host)}
  return hosts_list
end

def _ssh_to_vm
vm_entry = YAML.load_file("#{$vm_yaml_file}")
vms = vm_entry["vms"]
  for vm in vms
    `sed -i '/#{vm} /d' /root/.ssh/known_hosts`
    `echo -n "#{vm} " >> /root/.ssh/known_hosts`
    `echo -n "\`cat /opt/output/vm-template/vm-key\`\n" >>  /root/.ssh/known_hosts`
  end
  return vms
end

def _get_ds_path_escape(datastore_name)
  $dc_path, $dc_path_escape = _get_dc_path
  ds_path = ""
  ds_path_escape = ""
  datastores_path_escape = Shellwords.escape("/#{$vc_ip}/#{$dc_path}/datastores")
  ds_arr =  `rvc #{$vc_rvc} --path #{datastores_path_escape} -c 'find .' -c 'exit' -q`.encode('UTF-8', :invalid => :replace).split("\n")
  ds_arr.each do |ds|
    if ds[/#{Regexp.escape datastore_name}$/] and ds.partition(' ').last.gsub(/^.*\//,"") == datastore_name
      ds_path = "datastores/#{ds.partition(' ').last}"
    end
  end
  ds_path_escape = Shellwords.escape("/#{$vc_ip}/#{$dc_path}/#{ds_path}")
  ds_path = "/#{$vc_ip}/#{$dc_path}/" + ds_path
  return ds_path, ds_path_escape
end

def _is_vsan(datastore_name)
  ds_type_js = JSON.parse(`govc object.collect -dc "#{Shellwords.escape($dc_name)}" -json #{_get_moid("ds",datastore_name).join(':')} summary.type`.chomp)
  ds_type = ds_type_js[0]["val"]
  return (ds_type == "vsan")
end

def _is_ps_enabled(cluster_name = $cluster_name)
  return false if $compute_only_cluster == cluster_name
  vsan_stats_hash = _get_vsan_disk_stats(cluster_name)
  return vsan_stats_hash["PerfSvc"]
end

#returning {vsan_ds1 => {"capacity"=>cap,"freeSpace"=>fs,"local"=>true/false}, vsan_ds2 => {"capacity"=>cap,"freeSpace"=>fs,"local"=>true/false}}
def _get_vsandatastore_in_cluster(cluster_name = $cluster_name)
  return $vsandatastore_in_cluster if $vsandatastore_in_cluster != {}
  datastores_full_moid_in_cluster = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("cl",cluster_name).join(":")} datastore`.chomp.split(",")
  datastores_full_moid_in_cluster.each do |datastore_full_moid|
    if `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{datastore_full_moid} summary.type`.chomp == "vsan"
      ds_name = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{datastore_full_moid} name`.chomp
      ds_capacity = (`govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{datastore_full_moid} summary.capacity`.to_i/(1024**3)).to_s
      ds_freespace = (`govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{datastore_full_moid} summary.freeSpace`.to_i/(1024**3)).to_s
      $vsandatastore_in_cluster[ds_name] = {"capacity" => ds_capacity, "freeSpace" => ds_freespace, "local" => _is_ds_local_to_cluster(ds_name)}
    end
  end
  return $vsandatastore_in_cluster
end

def _get_ip_addr
  return $ip_Address
end

def _is_ip(ip)
  return !!(ip =~ Resolv::IPv4::Regex)
end

def _get_ip_from_hostname(hostname)
  address = ""
  begin
    address = IPSocket.getaddress(hostname)
  rescue Exception => e
    address = "Unresolvable"
  end
  return address
end

def _is_host_perfsvc_master(host)
  cmd = "python /usr/lib/vmware/vsan/perfsvc/vsan-perfsvc-status.pyc svc_info | grep 'isStatsMaster = true' | wc -l"
  host_key = $hosts_credential.has_key?(host) ? host : $hosts_credential.keys[0]
  host_username = $hosts_credential[host_key]["host_username"]
  host_password = $hosts_credential[host_key]["host_password"]
  return (ssh_valid(host,host_username,host_password) and ssh_cmd(host,host_username,host_password,cmd).chomp == "1") ? true : false 
end


#TBD CHECK HOST_CRED MATCHING HOSTNAME
def _get_perfsvc_master_node(cluster_name = $cluster_name)
  hosts_list = _get_hosts_list(cluster_name)
  hosts_list.each do |host|
    return host if _is_host_perfsvc_master(host)
  end
  return ""
end

def _set_perfsvc_verbose_mode(verbose_mode,cluster_name = $cluster_name)
  cl_path, cl_path_escape = _get_cl_path(cluster_name)
  `rvc #{$vc_rvc} --path #{cl_path_escape} -c 'vsantest.perf.vsan_cluster_perfsvc_switch_verbose . #{verbose_mode}' -c 'exit' -q`
  return ($?.exitstatus == 0)
end

def _clean_perfsvc_stats(cluster_name = $cluster_name)
  cl_path, cl_path_escape = _get_cl_path(cluster_name)
  `rvc #{$vc_rvc} --path #{cl_path_escape} -c 'vsan.perf.stats_object_delete .' -c 'exit' -q`
  return ($?.exitstatus == 0)
end

def _start_perfsvc(cluster_name = $cluster_name)
  cl_path, cl_path_escape = _get_cl_path(cluster_name)
  `rvc #{$vc_rvc} --path #{cl_path_escape} -c 'vsan.perf.stats_object_create .' -c 'exit' -q`
  return ($?.exitstatus == 0)
end

# get ip pool if using static, otherwise return []
# only add the ips not being occupied
def _get_ip_pools
  return [] if not $static_enabled
  return $ip_pool if $ip_pool != []
  ip_range = IPAddr.new("#{$starting_static_ip}/#{$static_ip_size}")
  begin_ip = IPAddr.new($starting_static_ip)
  system("ifconfig -s eth1 0.0.0.0; ifconfig eth1 down; ifconfig eth1 up")
  ips = []
  ip_required = [_get_num_of_tvm_to_deploy,_get_num_of_vm_to_deploy].max + 1 
  while ips.size < ip_required and ip_range.include? begin_ip do
    find_ip_threads = []
    count = ips.size
    temp_ip_arr = []
    while count < ip_required and ip_range.include? begin_ip do
      temp_ip_arr << begin_ip.to_s
      begin_ip = begin_ip.succ()
      count += 1
    end
    temp_ip_arr.each do |ip_to_s|
      find_ip_threads << Thread.new{
        o = system("arping -q -D -I eth1 -c 5 #{ip_to_s}")
        if o # ip available
          $occupied_ips.delete(ip_to_s) if $occupied_ips.include? ip_to_s
          ips << ip_to_s if not ips.include? ip_to_s
        else #ip occupied
          $occupied_ips << ip_to_s if not $occupied_ips.include? ip_to_s
        end
      } 
    end
    find_ip_threads.each{|t|t.join}
  end
  ips = ips.sort_by{|s| s.split(".")[-1].to_i}
  if ips[0]
    $eth1_ip = ips[0]
    system("ifconfig -s eth1 #{$eth1_ip}/#{$static_ip_size}")
  end
  $ip_pool = ips[1..-1]
  return $ip_pool
end

#despite if any ip is occupied, whether the subnet itself is big enough
def _range_big_enough
  ip_range = IPAddr.new("#{$starting_static_ip}/#{$static_ip_size}")
  temp_ip = IPAddr.new($starting_static_ip)
  ip_required = [_get_num_of_tvm_to_deploy,_get_num_of_vm_to_deploy].max + 1
  for i in 1..ip_required 
    return false if not ip_range.include? temp_ip
    temp_ip = temp_ip.succ()
  end
  return true
end

#Would only called by pre-validation
def _get_num_of_tvm_to_deploy
  return $tvm_num if $tvm_num != 0
  $tvm_num = _get_deploy_hosts_list.size  
  return $tvm_num
end

########### GOVC??????????
#Would only called by pre-validation, 
def _get_num_of_vm_to_deploy
  return $vm_num if not $easy_run
  vsan_datastores = _get_vsandatastore_in_cluster
  test_vsan = (vsan_datastores == {} or (vsan_datastores.keys & $datastore_names).empty?) ? false : true
  if test_vsan
    vsan_stats_hash = _get_vsan_disk_stats(_pick_vsan_cluster_for_easy_run)
    num_of_dg = vsan_stats_hash["Total number of Disk Groups"]
    $cl_path, $cl_path_escape = _get_cl_path if $cl_path == ""
    witness = `rvc #{$vc_rvc} --path #{$cl_path_escape} -c 'vsantest.vsan_hcibench.cluster_info .' -c 'exit' -q | grep -E "^Witness Host:"`.chomp
    num_of_dg -= 1 if witness != ""
    $vm_num = $vsan_version == 1 ? num_of_dg * 2 : (_get_hosts_list & _get_hosts_list_by_ds_name($datastore_names[0])).count * 2 
  else
    $vm_num = (_get_hosts_list & _get_hosts_list_by_ds_name($datastore_names[0])).count * 2
  end
  return $vm_num 
end

def _pick_vsan_cluster_for_easy_run
  return $easy_run_vsan_cluster if $easy_run_vsan_cluster != ""
  vsan_datastores = _get_vsandatastore_in_cluster
  vsan_datastore_names = vsan_datastores.keys & $datastore_names
  remote_cluster = []
  vsan_datastore_names.each do |vsan_datastore_name|
    if vsan_datastores[vsan_datastore_name]["local"]
      $easy_run_vsan_cluster = _get_vsan_cluster_from_datastore(vsan_datastore_name)
      return $easy_run_vsan_cluster
    else
      remote_cluster << _get_vsan_cluster_from_datastore(vsan_datastore_name)
    end
  end
  $easy_run_vsan_cluster = remote_cluster[0]
  return $easy_run_vsan_cluster
end

def _is_ds_local_to_cluster(datastore_name)
  datastore_alias_id =`govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("ds",datastore_name).join(":")} info.aliasOf`.chomp.delete('-')
  datastore_container_id = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("ds",datastore_name).join(":")} info.containerId`.chomp.delete('-')
  cluster_json = JSON.parse(`govc object.collect -json -s #{_get_moid("cl",$cluster_name).join(":")} configurationEx`.chomp)  
  if cluster_json["vsanHostConfig"][0]["clusterInfo"]["enabled"] 
    $compute_only_cluster = $cluster_name if not cluster_json["vsanHostConfig"][0]["enabled"]
    cluster_id = cluster_json["vsanHostConfig"][0]["clusterInfo"]["uuid"].delete('-')
    return (cluster_id == datastore_container_id or cluster_id == datastore_alias_id)
  else
    return true
  end
end

# get the owner cluster of the datastore
def _get_vsan_cluster_from_datastore(datastore_name)
  $vsan_perf_diag = true
  datastore_alias_id =`govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("ds",datastore_name).join(":")} info.aliasOf`.chomp.delete('-')
  datastore_container_id = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("ds",datastore_name).join(":")} info.containerId`.chomp.delete('-')
  ds_hosts_list = _get_hosts_list_by_ds_name(datastore_name)
  ds_hosts_list.each do |host|
    cluster_id = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("hs",host).join(":")} config.vsanHostConfig.clusterInfo.uuid`.chomp.delete('-')
    if cluster_id == datastore_container_id or cluster_id == datastore_alias_id
      cluster_full_moid = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("hs",host).join(":")} parent`.chomp
      return `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{cluster_full_moid} name`.chomp
    end
  end
end

# get compliant [ds] of the storage policy
def _get_compliant_datastore_ids_escape(storage_policy = $storage_policy)
  policy_js = JSON.parse(`govc storage.policy.info -s -json $'#{storage_policy.gsub("'",%q(\\\'))}'`.chomp)
  compliant_ds_names = policy_js["policies"][0]["compatibleDatastores"] || []
  return compliant_ds_names.map!{|ds|_get_ds_id_by_name(ds)}
end

# return datastore ref_id
def _get_ds_id_by_name(datastore_name)
  return _get_moid("ds",datastore_name)[1]
end

#clusters have vsan datastores mounted to testing cluster and those datastores are used for testing
#may not include the local cluster if only testing against remote datastores
#this would be only useful for wb clear
def _get_all_vsan_lsom_clusters
  return $all_vsan_lsom_clusters if $all_vsan_lsom_clusters != []
  vsan_datastores = _get_vsandatastore_in_cluster
  if vsan_datastores == {}
    p "vSAN is not enabled!"
    return []
  else
    vsan_datastore_names = vsan_datastores.keys & $datastore_names
    if not vsan_datastore_names.empty?
      vsan_datastore_names.each do |vsan_datastore_name|
        $all_vsan_lsom_clusters = $all_vsan_lsom_clusters | [_get_vsan_cluster_from_datastore(vsan_datastore_name)]
      end
    end
  end
  return $all_vsan_lsom_clusters
end

#clusters have vsan datastores mounted to testing cluster and those datastores are used for testing
#also must include the local cluster
#this would be only useful for all the cases except wb clear
def _get_all_vsan_clusters
  return $all_vsan_clusters if $all_vsan_clusters != []
  vsan_datastores = _get_vsandatastore_in_cluster
  if vsan_datastores == {}
    p "vSAN is not enabled!"
    return []
    #vsan is enabled, pass over all the clusters with vsan enabled
    #if remote cluster is included, it must have remote ds for testing
    #local cluster is automatically included even w/o any vsan ds being tested
  else
    $all_vsan_clusters = [$cluster_name]
    vsan_datastore_names = vsan_datastores.keys & $datastore_names
    #we at least have one vsan ds to test
    if not vsan_datastore_names.empty?
      $vsan_perf_diag = true
      vsan_datastore_names.each do |vsan_datastore_name|
        $all_vsan_clusters =  $all_vsan_clusters | [_get_vsan_cluster_from_datastore(vsan_datastore_name)]
      end
    end
  end
  return $all_vsan_clusters
end

#returning policy_name, rules in []
def _get_vsan_default_policy(datastore_name)
  vsan_default_policy_id = `rvc #{$vc_rvc} --path #{_get_ds_path_escape(datastore_name)[1]} -c 'vsantest.spbm_hcibench.get_vsandatastore_default_policy .' -c 'exit' -q | grep "^ProfileId" | awk '{print $2}'`.chomp
  default_policy_hash = JSON.parse(`govc storage.policy.ls -json #{vsan_default_policy_id}`.chomp)
  policy_name = default_policy_hash["profile"][0]["name"]
  return policy_name, _get_storage_policy_rules(policy_name)
end

#returning rules of the storage policy in []
def _get_storage_policy_rules(storage_policy = $storage_policy)
  rules = []
  policy_js = JSON.parse(`govc storage.policy.info -s -json $'#{storage_policy.gsub("'",%q(\\\'))}'`.chomp)
  rules_js = policy_js["policies"][0]["profile"]["constraints"]["subProfiles"][0]["capability"]
  rules_js.each do |rule_json|
    rule_json['constraint'][0]['propertyInstance'].each do |prop_ins|
      rules << "#{rule_json['id']['namespace']}.#{rule_json['id']['id']}.#{prop_ins['id']}: #{prop_ins['value']}"
    end
    #rules << "#{rule_json['Id']['Namespace']}.#{rule_json['Id']['Id']}: #{rule_json['Constraint'][0]['PropertyInstance'][0]['Value']}"
  end
  return rules
end

def _get_policy_rule_map(rules)
  policy_rule_map = {}
  rules.each do |rule|
    rule = rule.delete(' ')
    policy_rule_map[rule.split(":").first] = rule.split(":").last if not rule.include? "Rule-Set"
  end
  return policy_rule_map
end

#returning vsan disk stats detail table stats, sum stats
def _get_vsan_disk_stats(cluster_name = $cluster_name)
  cl_path, cl_path_escape = _get_cl_path(cluster_name)
  vsan_disk_stats_hash = eval(`rvc #{$vc_rvc} --path #{cl_path_escape} -c "vsantest.vsan_hcibench.get_vsan_disks_stats ." -c 'exit' -q`.chomp)
  `govc vsan.info -json -dc "#{Shellwords.escape($dc_name)}" "#{Shellwords.escape(cluster_name)}" > null 2>&1`
  return {} if $? != 0
  vsan_stats_hash = JSON.parse(`govc vsan.info -json -dc "#{Shellwords.escape($dc_name)}" "#{Shellwords.escape(cluster_name)}"`.chomp)
  cluster_vsan_hash = vsan_stats_hash["clusters"][0]
  cache_num = vsan_disk_stats_hash["cache_num"]
  cache_size = vsan_disk_stats_hash["cache_size"]
  capacity_num = vsan_disk_stats_hash["capacity_num"]
  capacity_size = vsan_disk_stats_hash["capacity_size"]
  total_usable_capacity = vsan_disk_stats_hash["capacity_size"] - vsan_disk_stats_hash["capacity_used"]
  at_rest_encryption = (cluster_vsan_hash["info"]["DataEncryptionConfig"]["EncryptionEnabled"].nil? or cluster_vsan_hash["info"]["DataEncryptionConfig"]["EncryptionEnabled"] == false) ? false : true 
  in_transit_encryption = (cluster_vsan_hash["info"]["DataInTransitEncryptionConfig"]["Enabled"].nil? or cluster_vsan_hash["info"]["DataInTransitEncryptionConfig"]["Enabled"] == false) ? false : true
  type = vsan_disk_stats_hash["vsan_type"] 
  dedupe_scope = vsan_disk_stats_hash["dedupe_scope"]
  perfsvc = cluster_vsan_hash["info"]["PerfsvcConfig"]["Enabled"] 
  verbose_mode = perfsvc ? cluster_vsan_hash["info"]["PerfsvcConfig"]["VerboseMode"] : false
  $vsan_version = vsan_disk_stats_hash["vsan_version"]
 
  return {"PerfSvc"=> perfsvc, "PerfSvc_verbose" => verbose_mode, "Total_Cache_Size"=> cache_size, "Total number of Disk Groups"=> cache_num, "Total number of Capacity Drives"=> capacity_num, "Total_Capacity_Size"=>capacity_size, "Total_Usable_Capacity"=>total_usable_capacity, "vSAN type"=>type,"Dedupe Scope"=> dedupe_scope, "Data at-Rest Encryption" => at_rest_encryption, "Data in-Transit Encryption" => in_transit_encryption} 
end

def _get_cluster_hosts_map_from_file(test_case_path)
  cluster_hosts_map = {}
  Dir.entries(test_case_path).select {|entry| File.directory? File.join(test_case_path,entry) and !(entry =='.' || entry == '..') and entry =~ /iotest-/}.each do |ioFolder|
    filename = test_case_path + "/#{ioFolder}/cluster_hosts_map.cfg"
    if File.exist? filename
      file_data = File.open(filename).read
      cluster_hosts_map = eval(file_data)
    else
      cluster_hosts_map = _get_cluster_hosts_map
      File.open(filename, "w") { |f| f.write cluster_hosts_map.to_s }
    end
  end
  return cluster_hosts_map
end

#returning has {cluster1 => [hosts...], cluster2 => [hosts...]}
def _get_cluster_hosts_map
  return $cluster_hosts_map if $cluster_hosts_map != {}
  @vsan_clusters = _get_all_vsan_clusters
  if not @vsan_clusters.empty?
    @vsan_clusters.each do |vsan_cluster|
      $cluster_hosts_map[vsan_cluster] = _get_hosts_list(vsan_cluster)
    end
  else
    $cluster_hosts_map[$cluster_name] = _get_hosts_list
  end
  return $cluster_hosts_map
end

# returning spare resource info of host in [cpu,ram_in_GB]
def _get_host_spare_compute_resource(host)
  resource_capacity = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("hs",host).join(":")} hardware.cpuInfo.numCpuThreads hardware.memorySize`.chomp.split("\n")
  host_cpu = resource_capacity[0].to_i
  host_ram = resource_capacity[1].to_f/(1024**2)
  vm_total_cpu = 0
  vm_total_ram = 0
  vms_moid = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("hs",host).join(":")} vm`.chomp.split(",")
  vms_moid.each do |vm_moid|
    vm_arr = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{vm_moid} config.hardware.numCPU config.hardware.memoryMB runtime.powerState`.chomp.split("\n").reverse()
    if vm_arr[0] == "poweredOn"
      vm_total_cpu += vm_arr[1].to_i
      vm_total_ram += vm_arr[2].to_f
    end
  end
  return [host_cpu-vm_total_cpu,((host_ram-vm_total_ram)/1024).to_i]
end

def _get_resource_used_by_guest_vms(host)
  vm_total_res = [0,0]
  vms_moid = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("hs",host).join(":")} vm`.chomp.split(",")
  vms_moid.each do |vm_moid|
    vm_arr = `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{vm_moid} name config.hardware.numCPU config.hardware.memoryMB runtime.powerState`.chomp.split("\n").reverse()
    if vm_arr[0] == "poweredOn" and vm_arr[1] =~ /^#{$vm_prefix}-/
      vm_total_res[0] += vm_arr[2].to_i
      vm_total_res[1] += (vm_arr[3].to_f/1024).to_i
    end
  end
  return vm_total_res
end

# returning datastore capacity and free space
def _get_datastore_capacity_and_free_space(datastore_name)
  #puts `govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("ds",datastore_name).join(":")} summary.capacity`
  ds_capacity = (`govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("ds",datastore_name).join(":")} summary.capacity`.to_i/(1024**3)).to_s
  ds_freespace = (`govc object.collect -dc "#{Shellwords.escape($dc_name)}" -s #{_get_moid("ds",datastore_name).join(":")} summary.freeSpace`.to_i/(1024**3)).to_s
  return ds_capacity,ds_freespace
end

def _get_vsan_support_url(cluster_name = $cluster_name)
  cl_path, cl_path_escape = _get_cl_path(cluster_name)
  support_url = `rvc #{$vc_rvc} --path #{cl_path_escape} -c "vsantest.perf.get_vsan_support_url ." -c 'exit' -q`.chomp
  return support_url.gsub("<VCENTER_IP>",$vc_ip)
end

def _get_res_avg_usage(startTime,endTime)
  cluster_hash = {}
  _get_cluster_hosts_map
  $cluster_hosts_map.keys.each do |cluster_name|
    cl_path, cl_path_escape = _get_cl_path(cluster_name)
    res_avg = `rvc #{$vc_rvc} --path #{cl_path_escape} -c "perf.stats_with_timerange -s #{startTime} -e #{endTime} -i '' cpu.usage,cpu.utilization,mem.usage -a 65535 -o avgs hosts/*" -c 'exit' -q`.chomp
    cluster_hash[cluster_name] = JSON.parse res_avg.gsub('=>', ':') 
  end
  return cluster_hash
end

def _get_res_usage(startTime,endTime,path)
  filename = path + "/resource_util.info"
  if File.exist? filename
    return File.open(filename).read
  end
  res_usage_table = "" #Terminal::Table.new
  cluster_hash = {}
  _get_cluster_hosts_map
  $cluster_hosts_map.keys.each do |cluster_name|
    cl_path, cl_path_escape = _get_cl_path(cluster_name)
    resUsage = `rvc #{$vc_rvc} --path #{cl_path_escape} -c "perf.stats_with_timerange -s #{startTime} -e #{endTime} -i '' cpu.usage,cpu.utilization,mem.usage -o table -a 65535 hosts/*" -c 'exit' -q`
    res_usage_table += resUsage
  end
  File.open(filename, "w") { |f| f.write res_usage_table + "\n\ncpu.usage - Provides statistics for logical CPUs. This is based on CPU Hyperthreading.\ncpu.utilization - Provides statistics for physical CPUs." }
  return res_usage_table + "\n\ncpu.usage - Provides statistics for logical CPUs. This is based on CPU Hyperthreading.\ncpu.utilization - Provides statistics for physical CPUs."
end

#Convert a string to a unicode string.
def _convert2unicode(str)
    strNew = ""
    str.split('').each { |c| strNew = strNew + '\\u' + c.ord.to_s(16).rjust(4,'0') }
    return strNew
end

def _get_vsan_health_summary(cluster_name = $cluster_name)
  cl_path, cl_path_escape = _get_cl_path(cluster_name)
  vsan_health_summary = `rvc #{$vc_rvc} --path #{cl_path_escape} -c "vsan.health.health_summary ." -c 'exit' -q`.chomp
  return vsan_health_summary
end

def _create_shared_folder(export_path,share_folder_name)
   $vsan_debug_sharing_path = export_path + "/#{share_folder_name}"
   if File.exists?($vsan_debug_sharing_path)
     FileUtils.rm_rf($vsan_debug_sharing_path)
   end
   Dir.mkdir($vsan_debug_sharing_path)

  return $vsan_debug_sharing_path
end

def _update_export_info(export_path)
  content = "#{export_path} *(rw,sync,no_root_squash,no_subtree_check,fsid=#{rand(999)})"
  File.write('/etc/exports',content)
  `exportfs -r`
end

def _remove_export_info(export_path)
  FileUtils.rm_rf(export_path)
  `> /etc/exports;exportfs -r`
end

def _unmount_nfs_from_esxi(host)
  unmount_cmd = "localcli storage nfs remove --volume-name hcibench-volume"
  host_key = $hosts_credential.has_key?(host) ? host : $hosts_credential.keys[0]
  host_username = $hosts_credential[host_key]["host_username"]
  host_password = $hosts_credential[host_key]["host_password"]
  if ssh_valid(host,host_username,host_password)
    ssh_cmd(host,host_username,host_password,unmount_cmd)
  end
end

def _mount_nfs_to_esxi(host)
  mount_cmd = "localcli storage nfs add --host #{$ip_Address} -s #{$vsan_debug_sharing_path} -v hcibench-volume"
  create_subfolder_cmd = "mkdir /vmfs/volumes/hcibench-volume/#{host}"
  host_key = $hosts_credential.has_key?(host) ? host : $hosts_credential.keys[0]
  host_username = $hosts_credential[host_key]["host_username"]
  host_password = $hosts_credential[host_key]["host_password"]
  if ssh_valid(host,host_username,host_password)
    _unmount_nfs_from_esxi(host)
    ssh_cmd(host,host_username,host_password,mount_cmd)
    ssh_cmd(host,host_username,host_password,create_subfolder_cmd)
  end
end

def _convert_perf_stats_to_json(file_path, metric_name)
  header = '--------------SOAP stats dump--------------'
  separator = '--------------Stats Segment Separator--------------'
  soap_dump = File.read(file_path)
  xml_segments = soap_dump.sub(header, '').split(separator).map(&:strip).reject(&:empty?)
  xml_segments.map do |xml_segment|
    xml_segment.each_line do |line|
      if line.include? metric_name
        doc = Nokogiri::XML(line) { |config| config.noblanks.strict }
        xml_hash = Hash.from_xml(+doc.to_s)
        return JSON.parse(xml_hash.to_json)['obj']['VsanPerfEntityMetricCSV']
      end
    end
  end
end

def _get_resource_util_from_perf_stats(bundle_path,metric_name,metric_type)
  map_file_path = bundle_path + "/cmmds-tool_find--f-python.txt"
  perf_stats_path = bundle_path + "/perf-stats.txt"
  map_file = File.read(map_file_path)
  perf_stats_file = File.read(perf_stats_path)
  
  host_hash = {}
  last_comma_index = map_file.rindex(',')
  if last_comma_index && last_comma_index != map_file.length - 1
    map_file[last_comma_index] = ''
  end
  map_hash = JSON.parse(map_file)
  map_hash.each do |item|
    if item["type"] == "HOSTNAME"
      host_info = JSON.parse(item["content"])
      host_hash[item["uuid"]] = host_info["hostname"]
    end
  end
  json_output = _convert_perf_stats_to_json(perf_stats_path, metric_name)
  json_content = JSON.parse(json_output.to_json)
  resource_hash = {}
  json_content.each do |item|
    item["value"].each do |metric|
      if metric["metricId"]["label"] == metric_type
        value_arr = metric["values"].split(",")
        avg = value_arr.inject(0){|sum,x| sum + x.to_i }/ value_arr.size
        host_uuid = item["entityRefId"].split(":")[1]
        resource_hash[host_hash[host_uuid]] = avg
      end
    end
  end
  JSON.parse(resource_hash.to_json)
end
