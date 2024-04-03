#!/usr/bin/ruby
require_relative "util.rb"
require_relative "rvc-util.rb"

@hosts_list = []
@vsan_clusters = _get_all_vsan_lsom_clusters
@vsan_clusters.each do |vsan_cluster|
  _get_vsan_disk_stats(vsan_cluster)
  @hosts_list = @hosts_list | _get_hosts_list(vsan_cluster) if $vsan_version == 1
end
exit(200) if @hosts_list.empty?
@start_drop_cmd = 'rm -rf /tmp/dropcache.log; nohup python /tmp/dropCache.py -r -w --verbose > /dev/null 2>&1 &'
@drop_progress_cmd = 'ps -c | grep "dropCache.py" | grep "verbose" | wc -l'
@drop_cache_script = "/opt/automation/lib/dropCache.py"
@drop_cache_log = "#{$log_path}/drop-cache.log"
@failure = false

def run_cmd(host)
  `sed -i '/#{host} /d' /root/.ssh/known_hosts`
  
  host_key = $hosts_credential.has_key?(host) ? host : $hosts_credential.keys[0]   
  host_username = $hosts_credential[host_key]["host_username"]
  host_password = $hosts_credential[host_key]["host_password"]

  if ssh_valid(host, host_username, host_password)
    scp_item(host,host_username,host_password, @drop_cache_script,"/tmp")
    ssh_cmd(host,host_username,host_password,@start_drop_cmd)
    time_retry = 0
    puts "Starting dropping cache on #{host}", @drop_cache_log
    while true   
      if time_retry == 3
        puts "Issued drop cache on #{host}, but unable to SSH into #{host} anymore",@drop_cache_log
        @failure = true
        break
      end

      if not ssh_valid(host, host_username, host_password)
        puts "SSH to #{host} can't be established, retry...",@drop_cache_log
        time_retry = time_retry + 1
        sleep(5)
        next
      else
        return_code = ssh_cmd(host,host_username,host_password,@drop_progress_cmd).to_i
        #drop-cache still running
        if return_code == 2 
          download_item(host,host_username,host_password,"/tmp/dropcache.log","#{$log_path}/#{host}-dropCache.log")
          sleep(10)
        else
          puts "#{host} done drop cache",@drop_cache_log
          break
        end
      end
    end
  else
    puts "Unable to SSH to #{host}",@drop_cache_log
    @failure = true
  end
end

tnode = []
@hosts_list.each do |s|
  tnode << Thread.new{run_cmd(s)}
end
tnode.each{|t|t.join}

if @failure
  exit(250)
else
  exit
end
