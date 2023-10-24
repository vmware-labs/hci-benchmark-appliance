#!/usr/bin/ruby
require_relative "util.rb"
require_relative "rvc-util.rb"
require 'fileutils'

@master_hosts_list = []
@vsan_clusters = _get_all_vsan_clusters
if not @vsan_clusters.empty?
  @vsan_clusters.each do |vsan_cluster|
    @master_hosts_list = @master_hosts_list | [_get_perfsvc_master_node(vsan_cluster)]
  end
else
  puts "vSAN not enabled!", @collect_support_bundle_log
  exit(255)
end

@test_case_name = File.basename(File.expand_path("#{ARGV[0]}"))
@dest_folder = "#{ARGV[0]}/vm-support-bundle"

`mkdir -p #{@dest_folder}`

@vm_support_manifest_template = "/opt/automation/lib/vsan-perfsvc-stats-hcibench.mfx.template"
@vm_support_manifest_script = "/opt/automation/lib/vsan-perfsvc-stats-hcibench.mfx"
@vsan_perfsvc_status_script = "/opt/automation/lib/perf-svc-vsan1/vsan-perfsvc-status.py"
@collect_support_bundle_log = "#{$log_path}/supportBundleCollect.log"
@failure = false

start_time = ARGV[1] || ARGV[0].split('-')[-1].to_i
end_time = ARGV[2] || File.mtime("#{ARGV[0]}-res.txt").to_i

@update_start_time = "sed -i 's/START_TIME/#{start_time}/g' #{@vm_support_manifest_script}"
@update_end_time = "sed -i 's/END_TIME/#{end_time}/g' #{@vm_support_manifest_script}"

@cmd_delete_manifest = "rm -f /etc/vmware/vm-support/vsan-perfsvc-stats-hcibench.mfx"
@cmd_delete_vsan_perfsvc_status_script = "rm -f /tmp/vsan-perfsvc-status.py"
@determine_vsphere_version = "vmware -v | awk '{print $3}' | cut -d '.' -f1"

def run_cmd(host)
  `sed -i '/#{host} /d' /root/.ssh/known_hosts`
  host_key = $hosts_credential.has_key?(host) ? host : $hosts_credential.keys[0]   
  host_username = $hosts_credential[host_key]["host_username"]
  host_password = $hosts_credential[host_key]["host_password"]
  if ssh_valid(host, host_username, host_password)
    puts "Determine vSphere version on #{host}",@collect_support_bundle_log
    #vsphere 8
    vs_ver = ssh_cmd_with_return(host,host_username,host_password,@determine_vsphere_version).to_i
    puts "vSphere version: #{vs_ver}",@collect_support_bundle_log
    if vs_ver > 7
      @vsan_perfsvc_status_script = "/opt/automation/lib/perf-svc-vsan2/vsan-perfsvc-status.py"
    end

    puts "Uploading VM Support manifest to #{host}",@collect_support_bundle_log
    if not scp_item(host,host_username,host_password, @vm_support_manifest_script,"/etc/vmware/vm-support")
      puts "Unable to upload #{@vm_support_manifest_script} to #{host}:/etc/vmware/vm-support"
      @failure = true
      return 
    end

    puts "Uploading vsan-perfsvc-status script to #{host}",@collect_support_bundle_log
    if not scp_item(host,host_username,host_password, @vsan_perfsvc_status_script,"/tmp")
      puts "Unable to upload #{@vsan_perfsvc_status_script} to #{host}:/tmp"
      @failure = true
      return
    end

    puts "Downloading bundle from #{host}...", @collect_support_bundle_log
    `wget --output-document "#{@dest_folder}/#{host}-vm-support-bundle.tgz" --no-check-certificate --user '#{host_username}' --password '#{host_password}' https://#{host}/cgi-bin/vm-support.cgi?manifests=Storage:VSANMinimal%20Storage:VSANPerfHcibench`

    puts "Clean up manifest on #{host}", @collect_support_bundle_log
    ssh_cmd(host,host_username,host_password,@cmd_delete_manifest)

    puts "Clean up script on #{host}", @collect_support_bundle_log
    ssh_cmd(host,host_username,host_password,@cmd_delete_vsan_perfsvc_status_script)

    puts "Parse support bundle...", @collect_support_bundle_log
    `ruby /opt/automation/lib/parseSupportBundle.rb "#{@dest_folder}/#{host}-vm-support-bundle.tgz" "#{@test_case_name}"`
  else
    puts "Unable to SSH to #{host}",@collect_support_bundle_log
    @failure = true
  end
end

puts "Generating manifest file",@collect_support_bundle_log
FileUtils.cp @vm_support_manifest_template, @vm_support_manifest_script

puts "Updating the time range",@collect_support_bundle_log
system(@update_start_time)
system(@update_end_time)

tnode = []
@master_hosts_list.each do |s|
  tnode << Thread.new{run_cmd(s)}
end
tnode.each{|t|t.join}

`rm -f #{@vm_support_manifest_script}`

if @failure
  exit(250)
else
  exit
end
