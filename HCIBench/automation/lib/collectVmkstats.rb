#!/usr/bin/ruby
require_relative "util.rb"
require_relative "rvc-util.rb"

@dest_folder = ARGV[0]
@post_process = ARGV[1]

@hosts_list = []
@vsan_clusters = _get_all_vsan_clusters
if not @vsan_clusters.empty?
  @vsan_clusters.each do |vsan_cluster|
    @hosts_list = @hosts_list | _get_hosts_list(vsan_cluster)
  end
else
  puts "vSAN not enabled!",@collect_vmkstats_log
  exit(255)
end

@collect_vmkstats_script = "/opt/automation/lib/vmkstats/vmkstats.py"
@collect_vmkstats_log = "#{$log_path}/vmkstatsCollect.log"
@failure = false

def run_cmd(host)
  parent_folder = "/vmfs/volumes/hcibench-volume/#{host}"
  host_key = $hosts_credential.has_key?(host) ? host : $hosts_credential.keys[0]   
  host_username = $hosts_credential[host_key]["host_username"]
  host_password = $hosts_credential[host_key]["host_password"]
  `sed -i '/#{host} /d' /root/.ssh/known_hosts`
  if ssh_valid(host, host_username, host_password)
    puts "Uploading collection script to #{host}",@collect_vmkstats_log
    scp_item(host,host_username,host_password, @collect_vmkstats_script, parent_folder)
    puts "Start collecting vmkstats on #{host}", @collect_vmkstats_log
    ssh_cmd(host,host_username,host_password,"python #{parent_folder}/vmkstats.py -c default -o #{parent_folder} > #{parent_folder}/vmkstatsCollect.log 2>&1")
  else
    puts "Unable to SSH to #{host}",@collect_vmkstats_log
    @failure = true
  end
end

def post_process(host)
  host_key = $hosts_credential.has_key?(host) ? host : $hosts_credential.keys[0]   
  host_username = $hosts_credential[host_key]["host_username"]
  host_password = $hosts_credential[host_key]["host_password"]
  `sed -i '/#{host} /d' /root/.ssh/known_hosts`
  if ssh_valid(host, host_username, host_password)
    `python3 /opt/automation/lib/vmkstats/vmkstats_postprocess.py --jar /opt/automation/lib/vmkstats/vmcallstackview.jar --flamegraph -o #{@dest_folder}/#{host}/hcibench_vmkstats_dumpDir --scriptdir /opt/automation/lib/vmkstats/`
    #ssh_cmd(host,host_username,host_password,@clear_vmkstats)
  else
    puts "Unable to SSH to #{host}",@collect_vmkstats_log
    @failure = true
  end
end

tnode = []
@hosts_list.each do |s|
  if @post_process == "true"
    tnode << Thread.new{post_process(s)}
  else
    tnode << Thread.new{run_cmd(s)}
  end
end
tnode.each{|t|t.join}

if @failure
  exit(250)
else
  exit
end
