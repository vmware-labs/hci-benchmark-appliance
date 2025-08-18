#/usr/bin/ruby
require 'yaml'
require 'fileutils'
require 'shellwords'
require_relative "rvc-util.rb"
require_relative "util.rb"
require_relative "#{$generatereport}"
require_relative "#{$getvsaninfo}"
require "cgi"

@folder_path_escape = _get_folder_path_escape[0]
@status_log_file = "#{$log_path}/test-status.log"
@log_file = "#{$log_path}/#{$tool}-testing.log"
@vc_username = $vc_username.gsub("\\","\\\\\\").gsub('"','\"')
@vc_password = $vc_password.gsub("\\","\\\\\\").gsub('"','\"')
@dc_path_pass = $dc_path.gsub("\\","\\\\\\").gsub('"','\"')
@ip_Address = _get_ip_addr
@ip_url = @ip_Address
@ip_url = "[" + @ip_Address + "]" if IPAddress.valid_ipv6? @ip_Address
@http_place = "https://#{@ip_url}:443/output/results"
@sleep_time = 1800
@debug_mode = $vsan_debug
@vsan_clusters_for_debug = [$cluster_name]
@vmk_collected = false

vsan_datastores = _get_vsandatastore_in_cluster
vsan_datastore_names = vsan_datastores.keys & $datastore_names

#at least one vsan datastore in test
if vsan_datastore_names != []
  $telegraf_target_clusters_map[$cluster_name] = CGI.escape($cluster_name) if not $telegraf_target_clusters_map.key?($cluster_name) and _is_ps_enabled($cluster_name)
  vsan_datastore_names.each do |vsan_datastore_name|
    cluster_name = _get_vsan_cluster_from_datastore(vsan_datastore_name)
    @vsan_clusters_for_debug = @vsan_clusters_for_debug | [cluster_name]
    $observer_target_clusters_arr = $observer_target_clusters_arr | [cluster_name]
    $telegraf_target_clusters_map[cluster_name] = CGI.escape(cluster_name) if not $telegraf_target_clusters_map.key?(cluster_name) and _is_ps_enabled(cluster_name)
  end
end

#whether to call vsan performance diagnostic, it should only be called when testing on vsan ds
@vsan_perf_diag = $vsan_perf_diag

if !$self_defined_param_file_path or !File.directory?($self_defined_param_file_path)
  $self_defined_param_file_path = "/opt/automation/#{$tool}-param-files"
end

duration_var = ""
if $testing_duration and $testing_duration.is_a?(Integer)
  duration_var = "--short-duration #{$testing_duration}"
end

def collectVmkStats(res_path,sleep_time)
  sleep(sleep_time)
  puts "Create NFS Share on HCIBench, the path is /tmp/#{$share_folder_name}",@log_file
  _create_shared_folder("/tmp",$share_folder_name)
  puts "Update NFS Exports Info...",@log_file
  _update_export_info("/tmp/#{$share_folder_name}")
  puts "Mount Shared Folder to Hosts...",@log_file
  `ruby /opt/automation/lib/prep-host-vsan-debug.rb /tmp/#{$share_folder_name} false`
  
  `ruby /opt/automation/lib/collectVmkstats.rb #{res_path} "false"`
  @vmk_collected = true  
  puts "Unmount Shared Folder from Hosts...",@log_file
  `ruby /opt/automation/lib/prep-host-vsan-debug.rb /tmp/#{$share_folder_name} true`
  _remove_export_info
end

def processVmkStats(res_path)
  `mv /tmp/#{$share_folder_name}/* #{res_path}`
  `ruby /opt/automation/lib/collectVmkstats.rb #{res_path} "true"`
end

def collectSupportBundle(res_path, start_time, end_time)
  `ruby /opt/automation/lib/collectSupportBundle.rb #{res_path} #{start_time} #{end_time}`
end

def snapshot(before_creation, num_ss, sleep_time, delete_after_creation)
  sleep(before_creation)
  `ruby /opt/automation/lib/vsan-tests/create-snapshots.rb #{num_ss} #{sleep_time}`
  sleep(delete_after_creation)
  `ruby /opt/automation/lib/vsan-tests/delete-snapshots.rb`
end

def generatePdf(path)
  `ruby /opt/automation/lib/generate_report.rb #{path}`
end

for item in Dir.entries($self_defined_param_file_path).sort
  File.delete($humbug_link_file) if File.exists?($humbug_link_file)
  item_log = "#{$log_path}/io-test-#{item}.log"
  next if item == '.' or item == '..' or File.directory?(item)

  if $clear_cache and vsan_datastore_names != []
    puts "Dropping Cache on All the Hosts", @status_log_file
    puts `ruby #{$dropcachefile}`,@log_file
    rc=$?.exitstatus
    if rc == 0
      puts "Cache Dropped",@status_log_file
    elsif rc == 200
      puts "vSAN ESA has no Host to Drop Cache",@status_log_file
    elsif rc == 250
      puts "[Caution] Dropping Cache Failed, Testing will be conducted",@status_log_file
    end
  end

  time = Time.now.to_i
  file_path = "#{$self_defined_param_file_path}/#{item}"
  FileUtils.mkdir_p "#{$output_path_dir}/#{item}-#{time}"
  path_testname = Shellwords.escape($output_path.gsub(".","-").gsub(" ","_"))
  path_testcase = Shellwords.escape(item.gsub(".","-").gsub(" ","_"))

  #Thread.start {snapshot(600,10,60,600)}

  #after testing running for sleep_time seconds, collect vmkstats, for vSAN engrs only.
  if @debug_mode 
    _create_shared_folder($output_path_dir + "/#{item}-#{time}",$share_folder_name)
    @vmk_collected = false
    Thread.start { collectVmkStats("#{$output_path_dir}/#{item}-#{time}",@sleep_time)}
  end
  cluster_path_arr = ""
  $observer_target_clusters_arr.each do |target_cluster|
    target_cluster_path_pass = _get_cl_path(target_cluster)[0].gsub("\\","\\\\\\").gsub('"','\"')
    cluster_path_arr += %{"/#{$vc_ip}/#{@dc_path_pass}/#{target_cluster_path_pass}" }
  end

  set_cluster_path_action_escape = Shellwords.escape(%{vsantest.perf.set_cluster_path #{cluster_path_arr}})
  set_username_action_escape = Shellwords.escape(%{vsantest.perf.set_vc_username "#{@vc_username}"})
  set_password_action_escape = Shellwords.escape(%{vsantest.perf.set_vc_password "#{@vc_password}"})

  puts %{Started Testing #{item}},@status_log_file
  puts %{<a href="http://#{@ip_url}:3000/d/#{$tool}/hcibench-#{$tool}-monitoring?orgId=1&var-Testname=#{path_testname}&var-Testcase=#{path_testcase}-#{time}" \
  target="_blank">HERE TO MONITOR #{$tool.upcase} PERFORMANCE</a>},@status_log_file

  if $telegraf_target_clusters_map != {}
    if $vsan_version == 1
      `ruby /opt/automation/lib/run_telegraf.rb`
      $telegraf_target_clusters_map.keys.each do |name|
        puts %{<a href="http://#{@ip_url}:3000/d/vsan/vsan-overview?orgId=1&refresh=10s&var-datasource=InfluxDB&var-cluster=#{$telegraf_target_clusters_map[name]}" \
        target="_blank">HERE TO MONITOR vSAN Cluster #{name} PERFORMANCE</a>},@status_log_file
      end
    else
      $telegraf_target_clusters_map.keys.each do |name|
        support_url = _get_vsan_support_url(name)
        puts %{<a href="#{support_url}" target="_blank">HERE TO MONITOR vSAN Cluster #{name} PERFORMANCE</a>},@status_log_file
      end
    end
  end

  `rvc #{$vc_rvc} --path #{@folder_path_escape} -c "vsantest.perf.set_vsan_perf_diag #{@vsan_perf_diag}" \
  -c #{set_username_action_escape} -c #{set_password_action_escape} -c #{set_cluster_path_action_escape} \
  -c 'vsantest.perf.runio_tests #{$vm_prefix}-* --num-vms #{$vm_num} --run-hcibench \
  --dir "#{$output_path_dir}"/#{item}-#{time} #{duration_var} --hcibench-param-file #{file_path} \
  --tool #{$tool}' -c 'exit' -q >> #{item_log} 2>&1`

  if $telegraf_target_clusters_map != {} and $vsan_version == 1
    `ruby /opt/automation/lib/stop_all_telegraf.rb`
  end

  puts %{Workload #{item} finished, preparing the results...},@status_log_file

  #copy over perf-conf.yaml and workload parameters to results folder
  puts `cp #{file_path} #{$output_path_dir}/#{item}-#{time}/#{$tool}.cfg`,@log_file
  `cp #{$basedir}/../conf/perf-conf.yaml #{$output_path_dir}/#{item}-#{time}/hcibench.cfg`
  `sed -i '/username/d' #{$output_path_dir}/#{item}-#{time}/hcibench.cfg`
  `sed -i '/password/d' #{$output_path_dir}/#{item}-#{time}/hcibench.cfg`
  resfile = "#{@http_place}/#{$output_path}/#{item}-#{time}-res.txt"
  #Collect the vsan info and save it to vsan.cfg
  #`ruby #{$getvsaninfo} #{$output_path_dir}/#{item}-#{time}/`
  cal_result_exe = "ruby #{$parsevdbfile} '#{$output_path_dir}'/'#{item}-#{time}' > '#{$output_path_dir}'/'#{item}-#{time}-res.txt' "
  if $tool == "fio"
    cal_result_exe = "ruby #{$parsefiofile} '#{$output_path_dir}'/'#{item}-#{time}' > '#{$output_path_dir}'/'#{item}-#{time}-res.txt' "
  end
  threads_arr = []
  threads_arr << Thread.new{`#{cal_result_exe} | tee -a #{@log_file}`}
  threads_arr << Thread.new{getVsanInfo("#{$output_path_dir}/#{item}-#{time}/")}
  if @debug_mode
    #puts "Unmount Shared Folder from Hosts...",@log_file
    #`ruby /opt/automation/lib/prep-host-vsan-debug.rb #{$output_path_dir}/#{item}-#{time}/#{$share_folder_name} true`    
    #_remove_export_info
    #collect support bundle
    end_time = Time.now.to_i
    threads_arr << Thread.new{collectSupportBundle("#{$output_path_dir}/#{item}-#{time}", time, end_time)}
    if @vmk_collected
      threads_arr << Thread.new{processVmkStats("#{$output_path_dir}/#{item}-#{time}/#{$share_folder_name}")} 
      puts %{Parsing Results, Collecting VM Support bundle from ESXi hosts and Parsing vmkstats files...},@status_log_file
    else
      puts %{Parsing Results and Collecting VM Support bundle from ESXi hosts...},@status_log_file
    end
  end
  threads_arr.each{|t|t.join}
  if File.exist?($humbug_link_file)
    link = File.read($humbug_link_file)
    `echo "\n\nvSAN Performance Stats Graph: #{link}" >> "#{$output_path_dir}/#{item}-#{time}-res.txt"`
  end
  if File.exist?($vsan_cpu_usage_file)
    `cp #{$vsan_cpu_usage_file} #{$output_path_dir}/#{item}-#{time}/`
  end
  puts %{Done Testing #{item}, Click <a href="#{resfile}" target="_blank">HERE</a> to view the result},@status_log_file
  puts %{Generating PDF Report...},@status_log_file
  genReport("#{$output_path_dir}/#{item}-#{time}")
end
