#!/usr/bin/ruby
require_relative "util.rb"
require_relative "rvc-util.rb"

@sharing_path = ARGV[0]
@post_process = ARGV[1]
@vsan_debug_log = "#{$log_path}/vsanDebug.log"

@hosts_list = []
@vsan_clusters = _get_all_vsan_clusters
if not @vsan_clusters.empty?
  @vsan_clusters.each do |vsan_cluster|
    @hosts_list = @hosts_list | _get_hosts_list(vsan_cluster)
  end
else
  puts "vSAN not enabled!",@vsan_debug_log
  exit(255)
end

@unmount_cmd = "localcli storage nfs remove --volume-name hcibench-volume"
@mount_cmd = "localcli storage nfs add --host #{$ip_Address} -s #{@sharing_path} -v hcibench-volume"

def post_process(host)
  host_key = $hosts_credential.has_key?(host) ? host : $hosts_credential.keys[0]
  host_username = $hosts_credential[host_key]["host_username"]
  host_password = $hosts_credential[host_key]["host_password"]
  `sed -i '/#{host} /d' /root/.ssh/known_hosts`
  if ssh_valid(host, host_username, host_password)
    puts "Unmounting sharing folder on #{host}", @vsan_debug_log 
    ssh_cmd(host,host_username,host_password,@unmount_cmd)
  else
    puts "Unable to SSH to #{host}",@vsan_debug_log
    @failure = true
  end
end

def run_cmd(host)
  host_key = $hosts_credential.has_key?(host) ? host : $hosts_credential.keys[0]   
  host_username = $hosts_credential[host_key]["host_username"]
  host_password = $hosts_credential[host_key]["host_password"]
  `sed -i '/#{host} /d' /root/.ssh/known_hosts`
  if ssh_valid(host, host_username, host_password)
    puts "Mounting sharing folder on #{host}", @vsan_debug_log
    ssh_cmd(host,host_username,host_password,@mount_cmd)
    puts "Create subfolder in share disk", @vsan_debug_log
    ssh_cmd(host,host_username,host_password,"mkdir /vmfs/volumes/hcibench-volume/#{host}")
  else
    puts "Unable to SSH to #{host}",@vsan_debug_log
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
