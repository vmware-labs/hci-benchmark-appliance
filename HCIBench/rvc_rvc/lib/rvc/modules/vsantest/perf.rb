require 'json'
require 'ipaddr'
require 'cgi'
require 'yaml'
require 'open-uri'
require 'rvc/vim'
require 'timeout'
require 'shellwords'
require 'rbvmomi/vsanmgmt.api'
require 'rbvmomi/vsanapiutils'

VIM::VirtualMachine

class VIM::VirtualMachine
  def take_screenshot file_name
    params = [
      "vm.screenshot",
      self.name,
      file_name
    ]
    params.join(" ")
    $shell.eval_command(params.join(" "))
  end

  def installvdbench
    cmds = ['cd /root/vdbench; unzip -q *; chmod +x ./vdbench',];
    self.runcmds(cmds)
  end

  def post_check
    cmd = "ls /sys/block | grep sd | wc -l"
    num = 0
    self.ssh do |ssh|
      num = ssh.exec!(cmd).delete!("\n").to_i - 1
    end
    if num == 0
      self.ssh do |ssh|
        num = ssh.exec!("ls /sys/block | grep nvme | wc -l").delete!("\n").to_i
      end
    end
    return num
  end

  def getipAddress
    ips = []
    ip_to_show = nil
    link_local_v6_ips = []
    nics = self.guest.net
    nics.each do |nic|
      nic.ipAddress.each do |nic_ip|
        if IPAddress.valid_ipv4? nic_ip
          ip_to_show = nic_ip
          break
        else
          ips << nic_ip
        end
      end
      break if ip_to_show
    end

    if not ip_to_show
      ips.each do |ipv6|
        if ipv6[0..3] != "fe80"
          ip_to_show = ipv6
          break
        else
          link_local_v6_ips << ipv6
        end
      end
    end
    begin
      ip_to_show = link_local_v6_ips[0] + "%eth1" if not ip_to_show
    rescue Exception => e
      puts "#{Time.now}: No IP is available on VM #{self.name}"
      ip_to_show = "IP_Not_Found"
    end
    puts "#{self.name}: #{ip_to_show}"
    @ipAddress ||= ip_to_show #self.guest.ipAddress
  end

  def ssh;
    Net::SSH.start(
      self.getipAddress, 'root',
      :password => 'vdbench',
      :verify_host_key => :never,
      :keepalive => true,
      :keepalive_interval => 60,
      :timeout => 60
    ) do |ssh|
      yield ssh
    end
  end

  def runcmds cmds
    self.ssh do |ssh|
      cmds.each do |cmd|
        puts "#{Time.now}: #{self.name}: Running '#{cmd}'"
        puts ssh.exec!(cmd)
      end
    end
  end

  def getresults path,tool
    download_path = ""
    download_type = ""
    if tool == "vdbench"
      download_path = "/root/vdbench/results.txt"
      download_type = "txt"
    elsif tool == "fio"
      download_path = "/root/fio/results.json"
      download_type = "json"
    end
    self.ssh do |ssh|
      puts "#{Time.now}: #{self.name}: Getting results"
      retries = 0
      begin
        ssh.scp.download!(download_path,"#{path}/#{self.name}.#{download_type}")
      rescue Exception => e
        puts "#{Time.now}: #{self.name}: Exception #{e}, retry..."
        retry if (retries += 1) < 3
      end
    end
  end

  def _runio path, params, opts = {};
    local_path = "/root/#{opts[:tool]}"
    if path[-1] == "/"
      path = path[0..-2]
    end
    output_folder_name = Shellwords.escape(path.split("/")[-2].gsub(".","-").gsub(" ","_"))
    testcase_name = Shellwords.escape(path.split("/")[-1].gsub(".","-").gsub(" ","_"))
    paramFileName = "vsan_perf"
    if opts[:paramFile]
      self.ssh do |ssh|
        puts "#{Time.now}: #{self.name}: uploading the params file"
        ssh.scp.upload! opts[:paramFile], local_path
      end
      paramFileName = File.basename(opts[:paramFile])
    end
    vmname = Shellwords.escape(self.name.gsub(".","-").gsub(" ","_"))
    duration_var_vdb = ""
    duration_var_fio = ""
    cmds = []
    if opts[:duration] != 0
      duration_var_vdb = "-e #{opts[:duration]}"
      duration_var_fio = "--runtime #{opts[:duration]}"
    end
    if opts[:tool] == "vdbench"
      cmds = [ #| sed 's/\\(^fe80:.*\\)\\($\\)/\\1%eth0\\2/'`; \
               "gip=`netstat -nptW | grep 'sshd' | awk '{print $5}' | rev | cut -d ':' -f2- | rev`; \
        cd /root/vdbench; export CARBON_HOST=${gip}; \
        export METRIC_PREFIX='vdbench.#{output_folder_name}.#{testcase_name}.#{vmname}'; \
        nohup ./vdbench -f #{paramFileName} #{duration_var_vdb} > results.txt 2>&1 & \
        python /root/graphites/vdbench_graphite.py /root/vdbench/results.txt > vdbench.graphite.log 2>&1"
               ]
    elsif opts[:tool] == "fio"
      cmds = [
        "gip=`netstat -nptW | grep 'sshd' | awk '{print $5}' | rev | cut -d ':' -f2- | rev`; \
        cd /root/fio; export CARBON_HOST=${gip}; \
        export METRIC_PREFIX='fio.#{output_folder_name}.#{testcase_name}.#{vmname}'; \
        > /root/fio/results.json;"
      ]
      if opts[:duration] != 0
        cmds[0] += "sed 's/runtime/#runtime/g' #{paramFileName} -i;"
      end
      cmds[0] += "nohup ./fio -f #{paramFileName} #{duration_var_fio} --status-interval=5 --lat_percentiles 1 \
      --output results.json --output-format=json > /root/fio/fio.log 2>&1 & sleep 2;\
      python /root/graphites/fio_graphite.py /root/fio/results.json > fio.graphite.log 2>&1"
    end
    self.runcmds(cmds);
    self.getresults(path,opts[:tool]);
  end

  def runio path, opts = {}
    params = []
    begin
      self._runio(
        path,
        params.join(" "),
        :duration => opts[:duration],
        #      :dev => opts[:dev],
        :paramFile => opts[:paramFile],
        :tool => opts[:tool]
      )
    rescue Exception => e
      puts "#{Time.now}: #{self.name}: Exception #{e}, taking screenshot to #{path}/#{self.name}.jpg"
      FileUtils.mkdir_p("#{path}/vm-troubleshooting")
      take_screenshot("#{path}/vm-troubleshooting/#{self.name}.jpg")
    end
  end
end

VIM::HostSystem

class VIM::HostSystem
  def runcmds cmds
    hostname = self.name
    self.ssh do |ssh|
      cmds.each do |cmd|
        puts "#{Time.now}: #{hostname}: Running '#{cmd}'"
        puts ssh.exec!(cmd)
      end
    end
  end

  def startVmkstats
    cmds = [
      "vsish -e set /perf/vmkstats/command/stop",
      "vsish -e set /perf/vmkstats/command/reset",
      "vsish -e set /perf/vmkstats/collectors/Default/enable",
      "vsish -e set /perf/vmkstats/collectors/worldlets/disable",
      "vsish -e set /perf/vmkstats/collectors/WorldYieldTarget/disable",
      "vsish -e set /perf/vmkstats/command/start",
    ]
    runcmds(cmds)
  end

  def stopVmkstats(dir)
    cmds = [
      "vsish -e set /perf/vmkstats/command/stop",
      "rm -f /root/vmkstats.tar.gz",
      "rm -rf /root/vmkstats",
      "mkdir /root/vmkstats",
      "vmkstatsdumper -d",
      "vmkstatsdumper -a -o /root/vmkstats/",
      "tar -czf /root/vmkstats.tar.gz /root/vmkstats",
      "rm -rf /root/vmkstats",
    ]
    runcmds(cmds)

    hostname = self.name
    self.ssh do |ssh|
      puts "#{Time.now}: #{hostname}: Downloading vmkstats.tar.gz to #{dir}"
      ssh.scp.download!("/root/vmkstats.tar.gz",
                        "#{dir}/#{hostname}-vmkstats.tar.gz")
    end
  end
end

opts :install_scripts do
  summary "Installs graphite scripts on VMs"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
end

def install_scripts vms
  vdb_graphite = "/opt/output/vm-template/graphites/vdbench_graphite.py"
  fio_graphite = "/opt/output/vm-template/graphites/fio_graphite.py"
  vms.each do |x|
    puts "#{Time.now}: #{x.name}: uploading graphites scripts to #{x.name}"
    x.ssh do |ssh|
      ssh.scp.upload!(vdb_graphite, "/root/graphites/")
      ssh.scp.upload!(fio_graphite, "/root/graphites/")
    end
  end
end

opts :install_vdbench do
  summary "Installs vdbench on VMs"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
end

def install_vdbench vms
  vdfile = Dir["/opt/output/vdbench-source/*.zip"][0]
  vms.each do |x|
    puts "Configuring VDBENCH on #{x.name}"
    x.ssh do |ssh|
      puts "#{Time.now}: #{x.name}: uploading the vdbench zip file"
      ssh.scp.upload!(vdfile, "/root/vdbench/")
    end
    x.installvdbench
  end
end

opts :install_fio do
  summary "Installs fio on VMs"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
end

def install_fio vms
  fiofile = "/opt/output/fio-source/fio"
  vms.each do |x|
    puts "Configuring FIO on #{x.name}"
    x.ssh do |ssh|
      puts "#{Time.now}: #{x.name}: uploading the fio file"
      ssh.scp.upload!(fiofile, "/root/fio/")
    end
  end
end

opts :install_diskinit do
  summary "Installs diskinit on VMs"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
end

def install_diskinit vms
  # Parameters
  filename = 'diskinit.tar.gz'
  dir_local = '/opt/output/vm-template/diskinit/'
  dir_remote = '/root/diskinit/'
  file_local = File.join(dir_local, filename)
  file_remote = File.join(dir_remote, filename)
  cmd = "/bin/tar -xvf #{file_remote} --strip 1 -C #{dir_remote} "\
    "&& cd #{dir_remote} "\
    "&& /bin/python setup.py install --record install.log"

  vms.each do |x|
    puts "Uploading diskinit to #{x.name}"
    x.ssh do |ssh|
      puts "#{Time.now}: #{x.name}: uploading tar file"
      ssh.scp.upload!(file_local, dir_remote)
      ssh.exec!(cmd)
    end
  end
end

opts :add_data_disk do
  summary "Adds a data disk(s) to each VM"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
  opt :no_thin, 'Use thick provisioning', :type => :boolean
  opt :size_gb, "Size of disk in GB", :default => 10, :type => :integer
  opt :num, "Number of disks", :default => 10, :type => :integer
  opt :add_ctrlr, "If need to add ctrlr", :type => :boolean
  opt :ctrlr_type, "vController type, pvscsi or nvme", :default => "pvscsi", :type => :string
  opt :profile_id, "Id of storage policy", :type => :string
  opt :multi_writer, "whether do multi_writer", :default => false, :type => :boolean
end

def add_data_disk vms, opts
  profile_id = ""
  profile_id = "--profile-id #{opts[:profile_id]} " if opts[:profile_id] and opts[:profile_id] != ""
  num_ctrlr = [(opts[:num].to_f/4).ceil,3].min
  disk_num_pvs_more = 0
  disk_num_pvs_less = 0
  num_pvs_more = opts[:num] % num_ctrlr
  num_pvs_less = num_ctrlr - num_pvs_more
  disk_num_pvs_more = opts[:num] / num_ctrlr + 1 if num_pvs_more != 0 #disks distribution not even
  disk_num_pvs_less = opts[:num] / num_ctrlr
  ctrlr_seq = "3100"
  ctrlr_seq = "100" if opts[:ctrlr_type] == "pvscsi"
  if opts[:add_ctrlr]
    vms.each do |x|
      $shell.fs.marks['foo'] = [x];
      for i in 1..num_ctrlr
        params = [
          "device.add_scsi_controller ",
          "-t #{opts[:ctrlr_type]} ",
        "~foo"]
        params.join(" ")
        $shell.eval_command(params.join(" "))
        sleep 1
      end
    end
  end

  vm_disk_map = {}
  num_vm_more_disk_create = opts[:num] % vms.size
  num_vm_less_disk_create = vms.size - num_vm_more_disk_create
  disk_num_create_more = 0
  disk_num_create_more = opts[:num] / vms.size + 1 if num_vm_more_disk_create != 0
  disk_num_create_less = opts[:num] / vms.size
  vms.each_with_index do |vm,vm_index|
    if vm_index < num_vm_more_disk_create
      vm_disk_map[vm.name] = [disk_num_create_more]
      vm_disk_map[vm.name] << opts[:num] - disk_num_create_more
    else
      vm_disk_map[vm.name] = [disk_num_create_less]
      vm_disk_map[vm.name] << opts[:num] - disk_num_create_less
    end
  end
  puts vm_disk_map if opts[:multi_writer]
  if opts[:multi_writer]
    $path_params = {}
    vms.each do |vm|
      stop_creating = false
      $shell.fs.marks['foo'] = [vm]
      disk_num = vm_disk_map[vm.name][0]
      for i in 0...num_ctrlr
        disk_num_deploy = disk_num_pvs_less
        disk_num_deploy = disk_num_pvs_more if i < num_pvs_more
        if opts[:ctrlr_type] == "pvscsi"
          ctrlr = i + 1
        else
          ctrlr = i
        end
        for j in 0...disk_num_deploy
          if disk_num > 0
            disk_num -= 1
          else
            stop_creating = true
            break
          end
          params = [
            "vsantest.vsan.device_add_disk",
            "-s #{opts[:size_gb]}Gi",
	    "--controller ~foo/devices/#{opts[:ctrlr_type]}-#{ctrlr_seq}#{ctrlr}/",
            "-f create",
            "-m",
            profile_id,
            "~foo"
          ]
          params << "--no-thin" #if opts[:no_thin]
          params.join(" ")
          $shell.eval_command(params.join(" "))
          sleep 1
        end
        break if stop_creating
      end
    end
  end

  vms.each_with_index do |x,vm_index|
    $shell.fs.marks['foo'] = [x];
    if opts[:add_ctrlr]
      existing_vmdk_num = 0
      local_path_params = []
      multi_writer_param = ""
      reuse_param = "-f create"
      if opts[:multi_writer]
        multi_writer_param = "-m"
        reuse_param = "-f reuse"
        $path_params.keys.each do |vm_name|
          if vm_name != x.name
            local_path_params = local_path_params | $path_params[vm_name]
          else
            existing_vmdk_num = $path_params[x.name].size
          end
        end
      end
      disk_num_deploy = 0

      puts "Adding #{opts[:num]} disks"
      path_param = ""
      for i in 0...num_ctrlr
        if i < num_pvs_more
          disk_num_deploy = disk_num_pvs_more
        else
          disk_num_deploy = disk_num_pvs_less
        end
        if opts[:ctrlr_type] == "pvscsi"
          ctrlr = i + 1
        else
          ctrlr = i
        end
        for j in 0...disk_num_deploy
          if existing_vmdk_num > 0
            existing_vmdk_num -= 1
            next
          end
          if opts[:multi_writer]
            path_param = "-p '" + local_path_params.pop + "'"
            puts path_param
          end
          params = [
            "vsantest.vsan.device_add_disk",
            "-s #{opts[:size_gb]}Gi",
	    "--controller ~foo/devices/#{opts[:ctrlr_type]}-#{ctrlr_seq}#{ctrlr}/",
            reuse_param,
            multi_writer_param,
            profile_id,
            path_param,
            "~foo"
          ]
          if opts[:no_thin]
            params << "--no-thin"
          end
          params.join(" ")
          $shell.eval_command(params.join(" "))
          sleep 1
        end
      end
    else # post-adding-disks
      #get current num of disks
      $shell.eval_command("vsantest.mark_hcibench.mark num ~foo/devices/disk*-#{ctrlr_seq}*")
      disk_num = $shell.eval_command("vsantest.mark_hcibench.count num")
      total_disk_num = opts[:num] + disk_num - 1

      num_ctrlr = [(total_disk_num.to_f/4).ceil,3].min
      $shell.eval_command("vsantest.mark_hcibench.mark #{opts[:ctrlr_type]} ~foo/devices/#{opts[:ctrlr_type]}-*")
      has_num_ctrlr = $shell.eval_command("vsantest.mark_hcibench.count #{opts[:ctrlr_type]}")

      while has_num_ctrlr < num_ctrlr
        params = [
          "device.add_scsi_controller ",
          "-t #{opts[:ctrlr_type]} ",
          "~foo"
        ]
        params.join(" ")
        $shell.eval_command(params.join(" "))
        sleep 1
        $shell.eval_command("vsantest.mark_hcibench.mark #{opts[:ctrlr_type]} ~foo/devices/#{opts[:ctrlr_type]}-*")
        has_num_ctrlr = $shell.eval_command("vsantest.mark_hcibench.count #{opts[:ctrlr_type]}")
      end
      disk_num_pvs_more = 0
      disk_num_pvs_less = 0
      num_pvs_more = total_disk_num % num_ctrlr
      num_pvs_less = num_ctrlr - num_pvs_more
      if num_pvs_more != 0 #disks distribution not even
        disk_num_pvs_more = total_disk_num / num_ctrlr + 1
      end
      disk_num_pvs_less = total_disk_num / num_ctrlr
      disk_num_deploy = 0

      for i in 0...num_ctrlr
        if i < num_pvs_more
          disk_num_deploy = disk_num_pvs_more
        else
          disk_num_deploy = disk_num_pvs_less
        end
        if opts[:ctrlr_type] == "pvscsi"
          ctrlr = i + 1
        else
          ctrlr = i
        end 
        
        has_disk_num = 0
        check_num = true
        begin
          $shell.eval_command("vsantest.mark_hcibench.mark num ~foo/devices/disk*-#{ctrlr_seq}#{ctrlr}-*")
        rescue Exception => e
          puts e
          check_num = false
        end

        if check_num
          has_disk_num = $shell.eval_command("vsantest.mark_hcibench.count num")
        end
        while has_disk_num < disk_num_deploy
          params = [
            "vsantest.vsan.device_add_disk ",
            "-s #{opts[:size_gb]}Gi",
            "--controller ~foo/devices/#{opts[:ctrlr_type]}-#{ctrlr_seq}#{ctrlr}/ ",
            profile_id,
            "~foo"
          ]
          if opts[:no_thin]
            params << "--no-thin"
          end
          params.join(" ")
          $shell.eval_command(params.join(" "))
          sleep 1
          $shell.eval_command("vsantest.mark_hcibench.mark num ~foo/devices/disk*-#{ctrlr_seq}#{ctrlr}-*")
          has_disk_num = $shell.eval_command("vsantest.mark_hcibench.count num")
        end
      end
    end
  end
  vms = vms.select{|x| x.runtime.powerState == "poweredOn"}
  if vms.length == 0
    return
  end
  puts "Rebooting VMs ..."
  vms.each do |x|
    x.RebootGuest
  end
  sleep(30)
  vms.each do |x|
    x.ssh{|ssh| puts ssh.exec!("uptime")}
  end
end

opts :set_esx_password do
  summary "Set ESX password"
  arg :password, "ESX Password", :default => 'cashc0w', :type => :string
end

def set_esx_password pw
  $esxpassword = pw
end

opts :set_vc_username do
  summary "Set VC Username"
  arg :username, "VC Username", :default => 'administrator@vsphere.local', :type => :string
end

def set_vc_username un
  $vcusername = un
end

opts :set_vc_password do
  summary "Set VC password"
  arg :password, "VC Password", :default => 'avmware', :type => :string
end

def set_vc_password pw
  $vcpassword = pw
end

opts :set_cluster_path do
  summary "Specify VSAN Cluster Path"
  arg :clusterpath, "VSAN Cluster Path", :type => :string, :multi => true
end

def set_cluster_path cp
  $clusterpath = cp
  puts "passed in #{$clusterpath.size} clusters"
end

opts :set_vsan_perf_diag do
  summary "whether enable the vsan performance diagnose function"
  arg :vsan_perf_diag, "enable or disable vsan performance diagnose", :type => :boolean, :default => false
end

def set_vsan_perf_diag vpd
  if vpd == "true"
    $vsan_perf_diag = true
  else
    $vsan_perf_diag = false
  end
end

def runObserver(vcip, path, opts, clusterpath);
  fork do
    Process.setpgrp()
    file_path = path + "/observer.json"


    if IPAddress.valid? vcip and IPAddress.valid_ipv6? vcip
      vc_rvc = Shellwords.escape("#{$vcusername}:#{$vcpassword}") + "@[#{vcip}]" + " -a"
    else
      vc_rvc = Shellwords.escape("#{$vcusername}:#{$vcpassword}") + "@#{vcip}" + " -a"
    end

    #  vc_rvc = Shellwords.escape("#{$vcusername}:#{$vcpassword}") + "@#{vcip}"
    cl_path_escape = Shellwords.escape("#{clusterpath}")
    exec("rvc #{vc_rvc} --path #{cl_path_escape} -c 'vsantest.vsan_hcibench.observer . -m 1 -e \"#{path}\"' -c 'exit' ")
  end
end

def runAnalyzerInt(path, params)
  $analyzerPath ||= "/build/trees/vsphere-2015/bora/vpx/tests/lib/stress_vpx/util/stress-vpx-json-analyse"
  dir=File.dirname(path)
  filename=File.basename(path);
  system("cd #{dir}; #{$analyzerPath} -g #{filename} #{params}")
end

def runAnalyzer(path)
  runAnalyzerInt(path, "")
end;

def runAnalyzerThread(path)
  fork do
    Process.setpgrp()
    sleep(120);
    runAnalyzerInt(path, "--forever --sleep 90 --graphTime 90");
  end
end

def runVmkstatsThread(host, dir)
  Thread.new do
    sleep(60);
    host.startVmkstats
    sleep(180)
    host.stopVmkstats(dir)
  end
end

def runVsanPerfDiagnostic path, vcip, opts = {}
  time_range_name = "HCIBench-" + path.rpartition('/')[-1]
  startTime = get_current_time_by_path[0]
  paramFile = opts[:paramFile]

  begin
    yield
  ensure
    if $vsan_perf_diag
      vsanPerfServiceEnabled = false
      ceip_enabled = false
      endTime = get_current_time_by_path[0]
      clusters = get_current_time_by_path[1..-1]
      diagnose_ui = false
      detail_dict =
        fileHtml =
        cluster = clusters[0]
      puts " #{_get_vc_version(cluster)[0]}, #{_get_vc_version(cluster)[1]}"
      if _get_vc_version(cluster)[1] >= 5575978 and _get_vc_version(cluster)[0] >= 6.5
        diagnose_ui = true
      end
      if diagnose_ui
        vc_uuid = _get_vc_uuid(cluster)
        begin
          Timeout::timeout(300) do
            if _vsan_perf_diagnose(cluster, "iops", startTime, endTime)
              ceip_enabled = true
            else
              puts "CEIP not turned on"
            end
          end
        rescue Timeout::Error => e
          puts e
          puts "CEIP not turned on or has issue to connect phone-home server"
          ceip_enabled = false
        end
        fileHtml = File.new("#{path}/performance_diagnostic_result.html", "w+")
        fileHtml.puts "<!DOCTYPE html><HTML><style>"
        clusters.each do |vsan_cluster|
          cluster_id = vsan_cluster.to_s.split("\"")[1].split("-")[1]
          fileHtml.puts ".#{cluster_id}_inv {display: none;}"
        end
        fileHtml.puts "</style><BODY>"
        detail_dict = get_supported_diag_exceptions(cluster)
      end
      clusters.each_with_index do |vsan_cluster,index|
        vsanPerfServiceEnabled = true if _save_time_range(vsan_cluster, startTime, endTime, time_range_name)
        cluster_name = _get_cluster_name(vsan_cluster)
        if diagnose_ui #when version is correct
          cluster_uuid = vsan_cluster.to_s.split("\"")[1]
          cluster_id = cluster_uuid.split("-")[1]
          url = "https://#{vcip}/ui/app/cluster;nav=h/urn:vmomi:ClusterComputeResource:#{cluster_uuid}:#{vc_uuid}/monitor/plugin/com.vmware.vsphere.client.h5vsan/com.vmware.vsan.client.h5vsanui.cluster.monitor.vsan.performance.diagnostics"
          if vsanPerfServiceEnabled and ceip_enabled
            fileHtml.puts "<h3>Select the category you want to improve for #{cluster_name}</h3><select id='#{cluster_id}_target'><option value='' selected disabled>Please select an option...</option>"
            fileHtml.puts "<option value='#{cluster_id}_iops'>To Get More I/O Per Second</option><option value='#{cluster_id}_tput'>To Get Better Throughput</option><option value='#{cluster_id}_lat'>To Get Lower Latency</option></select>"
            ceip_enabled = true
            for queryType in ["iops","tput","lat"]
              perf_diag_result = _vsan_perf_diagnose(vsan_cluster, queryType, startTime, endTime, paramFile)
              if queryType == "iops"
                fileHtml.puts "<div id='#{cluster_id}_iops' class='#{cluster_id}_inv'>"
              elsif queryType == "tput"
                fileHtml.puts "<div id='#{cluster_id}_tput' class='#{cluster_id}_inv'>"
              else
                fileHtml.puts "<div id='#{cluster_id}_lat' class='#{cluster_id}_inv'>"
              end
              if perf_diag_result and perf_diag_result != []
                vsan_disk_map = get_vsan_disks_info(vsan_cluster)
                exception_dgs = {}
                exception_rec = {}
                dg_labels = {}
                for entry in perf_diag_result
                  item = YAML.load(entry.to_yaml.gsub(/!ruby\S*$/,""))
                  exceptionId = item["props"][:exceptionId]
                  recommendation = item["props"][:recommendation]
                  #Assuming each exceptionId has only one recommendation
                  exception_rec[exceptionId] = recommendation if not exception_rec.has_key?(exceptionId)
                  #Add exception id into the hash as key if not added
                  if not exception_dgs.has_key?(exceptionId)
                    exception_dgs[exceptionId] = []
                    dg_labels = {}
                  end
                  if item["props"][:aggregationData]
                    dg = item["props"][:aggregationData]["props"][:entityRefId]
                    dg_labels[dg] = [] if not dg_labels.has_key?(dg)
                    for item_agData in item["props"][:aggregationData]["props"][:value]
                      label = item_agData["props"][:metricId]["props"][:label]
                      direction = item_agData["props"][:threshold]["props"][:direction]
                      threshold = item_agData["props"][:threshold]["props"][:yellow]
                      dg_labels[dg] << {"lable" => label, "direction" => direction, "threshold" => threshold}
                    end
                  else
                    for index_data in item["props"][:exceptionData]
                      dg = index_data["props"][:entityRefId]
                      dg_labels[dg] = [] if not dg_labels.has_key?(dg)
                      for index_label in index_data["props"][:value]
                        label = index_label["props"][:metricId]["props"][:label]
                        direction = index_label["props"][:threshold]["props"][:direction]
                        threshold = index_label["props"][:threshold]["props"][:yellow]
                        dg_labels[dg] << {"lable" => label, "direction" => direction, "threshold" => threshold}
                      end
                    end
                  end
                  exception_dgs[exceptionId] = dg_labels
                end
                for exceptionId in exception_dgs.keys
                  if detail_dict.has_key?(exceptionId)
                    fileHtml.puts "<h2>Potential Issue: #{detail_dict[exceptionId][0]}</h2>"
                    fileHtml.puts "Description: #{detail_dict[exceptionId][1]}"
                    fileHtml.puts "<a href=\"#{detail_dict[exceptionId][2]}\" target=\"_blank\" >Ask VMware</a>"
                  else
                    puts "Can't find exceptionId #{exceptionId} in all the exceptions"
                    puts exception_dgs
                  end
                end
              elsif perf_diag_result == []
                fileHtml.puts "<h2>No Potential Issue Found!</h2>"
              end
              fileHtml.puts "</div>"
            end
          end

          if ceip_enabled and vsanPerfServiceEnabled
            fileHtml.puts "<h3>Please go to <a href=\"#{url}\" target=\"_blank\">vCenter</a> and Cluster: #{cluster_name} to locate the time range named #{time_range_name} for more details</h3>"
          elsif vsanPerfServiceEnabled
            fileHtml.puts "<h3>Please go to <a href=\"#{url}\" target=\"_blank\">vCenter</a> to enable Customer Experience Improvement Program and in Cluster: #{cluster_name} to locate the time range named #{time_range_name} for more details</h3>"
          else
            fileHtml.puts "<h3>Please go to <a href=\"#{url}\" target=\"_blank\">vCenter</a> to enable Customer Experience Improvement Program and vSAN Performance Service to enable vSAN Performance Diagnostic, also make sure vCenter can reach out Internet</h3>"
          end
          fileHtml.puts "<script>document.getElementById('#{cluster_id}_target').addEventListener('change', function () {'use strict';"
          fileHtml.puts "var #{cluster_id}_vis = document.querySelector('.#{cluster_id}_vis');var target = document.getElementById(this.value);"
          fileHtml.puts "if (#{cluster_id}_vis !== null) {#{cluster_id}_vis.className = '#{cluster_id}_inv';}"
          fileHtml.puts "if (target !== null ) {target.className = '#{cluster_id}_vis';}});</script>"
        end
      end

      if diagnose_ui
        fileHtml.puts "</BODY></HTML>"
        fileHtml.close()
      end
    end
    puts "#{Time.now}: Testing Done"
  end
end

def runIoTest(vms, path, name, opts)
  vcip = vms.first._connection.host
  hosts = vms.map{|x| x.runtime.host}.uniq

  if opts[:oio]; name += "-oio#{opts[:oio]}"; end
  if opts[:nameSuffix]; name += "-#{opts[:nameSuffix]}"; end
  opts[:vms] = vms
  runVsanPerfDiagnostic(path, vcip, opts) do
    threads = vms.map do |v|
      thread = Thread.new do
        begin
          yield(v)
        rescue Exception => ex
          puts ex.backtrace
          puts ex
          pp "#{v.name}: #{ex.class}: #{ex.message}"
        end
      end
      [v, thread]
    end
    threads.each{|vm, t| t.join}
    threads.each do |vm, t|
      if t.alive?
        puts "#{Time.now}: ******** Thread of VM #{vm.name} is still alive"
      end
    end
    puts "#{Time.now}: Done running tests"
  end
end

def runIo(vms, path, opts)
  runIoTest(vms, path, "iotest", opts) do |vm|
    vm.runio(path, opts)
  end
end

def verify_credentials vcip, hostips
  if !_test_ssh(vcip, 'root', $vcpassword)
    err "VC password wrong or SSH login failed for other reasons"
  end
end

opts :run_commands do
  summary "Run Commands on VM(s)"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
  opt :cmd, "List of quote enclosed commands", :type => :string
end

def run_commands(vms, opts)
  vms.each do |vm|
    cmds = [opts[:cmd]]
    vm.runcmds(cmds)
  end
end

opts :runio_tests do
  summary "Run IO tests"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
  opt :dir, "Output directory", :type => :string
  opt :run_90r10w, "Run 70r30w workloads", :type => :boolean
  opt :run_70r30w, "Run 70r30w workloads", :type => :boolean
  opt :run_50r50w, "Run 50r50w workloads", :type => :boolean
  opt :run_30r70w, "Run 30r70w workloads", :type => :boolean
  opt :run_10r90w, "Run 10r90w workloads", :type => :boolean
  opt :run_writes, "Run write workloads", :type => :boolean
  opt :run_reads, "Run read workloads", :type => :boolean
  opt :run_long, "Run long running workloads", :type => :boolean
  opt :small_area, "Size (MB) of fit-into-ssd area per VM?", :default => 100, :type => :integer
  opt :short_duration, "Duration for short tests in seconds", :default => 0, :type => :integer
  opt :short_basic_oios, "OIO values, comma separated", :default => "4,16", :type => :string
  opt :short_iosizes, "IO sizes in B, comma separated", :default => "512,4096,16384,65536,262144", :type => :string
  opt :device, "Device inside VM to use", :default => '/dev/sdb', :type => :string
  opt :num_vms, "Number of VMs to use", :default => 10, :type => :integer
  opt :with_vmkstats, "Also run vmkstats. May reduce performance"
  opt :num_snapshots, "Number of snapshots to take", :default => 0, :type => :integer
  opt :snapshot_delay, "Delay between snapshots (seconds)", :default => 300, :type => :integer
  opt :snapshot_delete_onebyone, "Delete the created snapshots one-by-one", :type => :boolean
  opt :run_hcibench, "Run vdbench or fio with user defined paramas", :type => :boolean
  opt :hcibench_param_file, "Specify the path of user defined params file of vdbench or fio", :type => :string
  opt :tool, "Specify the tool will be used for testing", :default => "vdbench", :type => :string
end

def _test_ssh(host, user, password)
  begin
    Net::SSH.start(host, user, :password => password, :verify_host_key => :never) do |ssh|
      ssh.exec!("uname -a")
    end
  rescue
    return false
  end
  return true
end

def runio_tests vms, opts
  if vms.any?{|vm| vm.disks.length < 2}
    err "All VMs need a data disk"
  end
  if !opts[:dir]
    err "Must specify an output directory"
  end
  dir = opts[:dir]

  conn = vms.first._connection
  hosts = vms.map{|x| x.runtime.host}.uniq
  #  verify_credentials(conn.host, hosts.map{|x| x.name})

  small_area = "#{opts[:small_area] || 100}M"
  oioValues = opts[:short_basic_oios].split(",").map{|x| x.to_i}
  ioSizes = opts[:short_iosizes].split(",").map{|x| x.to_i}
  numVms = opts[:num_vms]

  if opts[:run_hcibench]
    runIo(vms[0..(numVms-1)], dir,
          :nameSuffix => "#{opts[:tool]}-#{numVms}vm",
          :duration => opts[:short_duration],
          :paramFile => opts[:hcibench_param_file],
          :tool => opts[:tool])
  end
end

opts :get_vm_count do
  summary "Get Number of VMs"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
end

def get_vm_count vms
  puts vms.size
end

opts :get_vm_datastore_map do
  summary "Display VM Datastore Hash"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
end

def get_vm_datastore_map vms
  ds = {}
  vms.each do |vm|
    datastores = vm.datastore
    datastores.each do |datastore_instance|
      datastore = datastore_instance.name
      if ds.key?(datastore)
        ds[datastore] << vm.name
      else
        ds[datastore] = [vm.name]
      end
    end
  end
  puts ds
end

opts :get_datastore_capacity_and_free_space do
  summary "get datastore capacity and free space"
  arg :ds, nil, :lookup => VIM::Datastore
end

def get_datastore_capacity_and_free_space datastore
  freespace = datastore.summary.freeSpace/(1024*1024*1024)
  capacity = datastore.summary.capacity/(1024*1024*1024)
  puts capacity
  puts freespace
end

opts :get_host_spare_compute_resource do
  summary "get host spare compute resource"
  arg :host, nil, :lookup => VIM::HostSystem
end

def get_host_spare_compute_resource host
  cpu_cores = host.hardware.cpuInfo.numCpuThreads
  ram_size = host.hardware.memorySize.to_f/(1024*1024)
  cpu_cores_used = 0
  ram_size_used = 0
  vms = host.vm
  vms.each do |vm|
    ram_size_used += vm.config.hardware.memoryMB
    cpu_cores_used += vm.config.hardware.numCPU
  end

  puts cpu_cores-cpu_cores_used
  puts ((ram_size-ram_size_used)/1024).floor

  return [cpu_cores-cpu_cores_used,(ram_size-ram_size_used)/1024] 
end

opts :get_resource_used_by_vms do
  summary "get used resource and the vm names"
  arg :host, nil, :lookup => VIM::HostSystem
end

def get_resource_used_by_vms host
  vms_resource_usage = {}
  vms = host.vm
  vms.each do |vm|
    vms_resource_usage[vm.name] = []
    vms_resource_usage[vm.name].push(vm.config.hardware.numCPU)
    vms_resource_usage[vm.name].push((vm.config.hardware.memoryMB/1024).floor)
  end
  puts vms_resource_usage
  return vms_resource_usage
end

opts :get_vm_resource_info do
  summary "get vm resource info"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
end

#{"vm1":[4,4,"network name","datastore name"], "vm2":[4,8,"network name","datastore name"]}
def get_vm_resource_info vms
  vm_resource_map = {}
  vms.each do |vm|
    vm_name = vm.name
    vm_cpu = vm.config.hardware.numCPU
    vm_ram = (vm.config.hardware.memoryMB/1024)
    ds_name = vm.datastore[0].name
    nt_name = vm.network[0].name
    vm_resource_map[vm_name] = [vm_cpu,vm_ram,nt_name,ds_name]
  end
  puts vm_resource_map
end


opts :get_vm_datastore_info do
  summary "Display VM Datastore"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
end

def get_vm_datastore_info vms
  ds = {}
  vms.each do |vm|
    datastores = vm.datastore
    datastores.each do |datastore_instance|
      datastore = datastore_instance.name
      if ds.key?(datastore)
        ds[datastore] = ds[datastore] + 1
      else
        ds[datastore] = 1
      end
    end
  end
  puts ds
end

opts :get_vm_network_info do
  summary "Display VM Network"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
end

def get_vm_network_info vms
  nt = {}
  vms.each do |vm|
    network = vm.network[0].name
    if nt.key?(network)
      nt[network] = nt[network] + 1
    else
      nt[network] = 1
    end
  end
  puts nt
end

opts :get_vm_network do
  summary "Display vms' network mapping"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
end

def get_vm_network vms
  vm_net_map = {}
  vms.each do |vm|
    if vm.summary.runtime.powerState == "poweredOn"
      network = vm.network[0]
      ip = vm.getipAddress
      vm_net_map[vm.name] = {network._ref => ip}
    end
  end
  puts vm_net_map
end


opts :find_hosts_in_maintainance do
  summary "Get hosts that in maintainance mode, if not return null"
  arg :cluster, nil, :lookup => VIM::ComputeResource
end

def find_hosts_in_maintainance cluster,
  hosts = cluster.host
  hosts_in_maintainance = []
  hosts.each do |host|
    if host.runtime.inMaintenanceMode
      hosts_in_maintainance << host.name
    end
  end
  puts hosts_in_maintainance
end

opts :find_vsan_datastore do
  summary "Get VSAN Datastore by specifing Cluster"
  arg :cluster, nil, :lookup => VIM::ComputeResource
end

def find_vsan_datastore cluster,
  cluster_id = cluster.configurationEx.vsanConfigInfo.defaultConfig.uuid.delete('-')
  datastores = {}
  cluster.datastore.each do |x|
    if x.class.to_s == "Datastore" and x.summary.type == "vsan"
      container_id = x.info.url.split("/")[-1].split(":")[1]
      ds_container_id = container_id.delete('-')
      datastores[x.name] = {"capacity"=>((x.summary.capacity).to_i/(1024*1024*1024)).to_s,"freeSpace"=>((x.summary.freeSpace).to_i/(1024*1024*1024)).to_s,"local"=>(ds_container_id == cluster_id)}
    end
  end
  puts datastores
end

def get_policy_id_by_name obj,name,
  found = false
  profiles = []
  id = ""
  conn = obj._connection
  pbm = conn.pbm
  pbm.rev = '2.0'
  pm = pbm.serviceContent.profileManager
  profileIds = pm.PbmQueryProfile(
    :resourceType => {:resourceType => "STORAGE"},
    :profileCategory => "REQUIREMENT"
    )
  if profileIds.length > 0
    profiles = pm.PbmRetrieveContent(:profileIds => profileIds)
  end

  if profiles.length > 0
    profiles.each do |profile|
      if profile.name == name
        found = true
        id =  profile[:profileId][:uniqueId]
      end
    end
  end
  id
end

opts :get_vsan_owner_cluster_from_datastore do
  summary "get vsan cluster owner of datastore"
  arg :datastore, nil, :lookup => VIM::Datastore
end

def get_vsan_owner_cluster_from_datastore datastore
  container_id = datastore.info.url.split("/")[-1].split(":")[1]
  ds_container_id = container_id.delete('-')
  hosts_list = datastore.host
  hosts_list.each do |host|
    cluster_uuid = host.key.parent.configurationEx.vsanConfigInfo.defaultConfig.uuid.delete('-')
    if cluster_uuid == ds_container_id
      puts host.key.parent.name
      return host.key.parent
    end
  end
end

opts :get_cluster_id do
  summary "Get cluster container id"
  arg :cluster, nil, :lookup => VIM::ComputeResource
end

def get_cluster_id cluster
  cluster_id = cluster.configurationEx.vsanConfigInfo.defaultConfig.uuid.delete('-')
  puts cluster_id
  return cluster_id
end

opts :get_vsan_datastore_container_id do
  summary "get vsan datastore container id"
  arg :datastore, nil, :lookup => VIM::Datastore
end

def get_vsan_datastore_container_id datastore
  container_id = datastore.info.url.split("/")[-1].split(":")[1]
  datastore_container_id = container_id.delete('-')
  puts datastore_container_id
  return datastore_container_id
end

opts :get_datastore_id do
  summary "Get compaliant datastores names by using policy name"
  arg :ds, nil, :lookup => VIM::Datastore
end

def get_datastore_id datastore
  puts datastore._ref
  return datastore._ref
end

opts :get_compliant_datastore_by_policy_name do
  summary "Get compaliant datastores names by using policy name"
  arg :dc, nil, :lookup => VIM::Datacenter
  arg :name, nil, :type => :string
end

def get_compliant_datastore_by_policy_name dc,name,
  conn = dc._connection
  pbm = conn.pbm
  pbm.rev = '2.0'
  ps = pbm.serviceContent.placementSolver
  ds_ids = []
  profile_id = get_policy_id_by_name(dc,name)
  if profile_id != ""
    datastores = ps.PbmQueryMatchingHub(
      :profile => {:uniqueId => profile_id}
      )
    if datastores.size != 0
      datastores.each do |ds|
        ds_ids << ds.hubId
      end
      puts ds_ids
    else
      puts "Cant find compliant datastore for policy #{name}"
    end
  else
    puts "Cant find the storage policy #{name}"
  end
end

opts :get_vsan_support_url do
  summary "get vc info"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource  
end

def get_vsan_support_url cluster
  cluster_moid = cluster._ref
  uuid = cluster._connection.serviceContent.about.instanceUuid
  em = cluster._connection.serviceContent.extensionManager
  vsan_client_version = ""
  em.extensionList.each do |ext_instance|
    if ext_instance.key == "com.vmware.vsan.client"
      vsan_client_version = ext_instance.client[0].version
      break
    end
  end
  puts "https://<VCENTER_IP>/ui/app/cluster;nav=h/urn:vmomi:ClusterComputeResource:#{cluster_moid}:#{uuid}/monitor/plugin/com.vmware.vsan.client/VC~com.vmware.vsan.client~#{vsan_client_version}~navigable~com.vmware.vsan.client.h5vsanui.cluster.monitor.vsan.performance"
end

opts :get_policy_instance_by_name do
  summary "Get storage policy by the name"
  arg :dc, nil, :lookup => VIM::Datacenter
  arg :name, nil, :type => :string
end

def get_policy_instance_by_name dc,name,
  found = false
  profiles = []
  policy = nil
  conn = dc._connection
  pbm = conn.pbm
  pbm.rev = '2.0'
  pm = pbm.serviceContent.profileManager
  profileIds = pm.PbmQueryProfile(
    :resourceType => {:resourceType => "STORAGE"},
    :profileCategory => "REQUIREMENT"
    )
  if profileIds.length > 0
    profiles = pm.PbmRetrieveContent(:profileIds => profileIds)
  end

  if profiles.length > 0
    profiles.each do |profile|
      if profile.name == name
        policy = profile
        break
      end
    end
  end
  policy
end

opts :get_policy_rules_by_name do
  summary "get vSAN storage rules by name"
  arg :dc, nil, :lookup => VIM::Datacenter
  arg :name, nil, :type => :string
end

def get_policy_rules_by_name dc,name,
  id = get_policy_id_by_name(dc,name)
  conn = dc._connection
  pbm = conn.pbm
  pbm.rev = '2.0'
  pm = pbm.serviceContent.profileManager
  if id
    prof_entity = pm.PbmRetrieveContent(:profileIds => [:uniqueId => id])
    prof_entity[0].display_info
  end
end

opts :get_storage_ref_by_name do
  summary "Get datastore ref id by name"
  arg :dc, nil, :lookup => VIM::Datacenter
  arg :name, nil, :type => :string
end

def get_storage_ref_by_name dc,name
  for datastore in dc.datastore
    if name == datastore.name
      puts datastore._ref
      return
    end
  end
  puts "NOT FOUND"
end

opts :get_hosts_by_ds do
  summary "Get all hosts that can access the datastore"
  arg :ds, nil, :lookup => VIM::Datastore
end

def get_hosts_by_ds ds
  hosts = []
  ds.host.each{|host| hosts << host.key.name}
  puts hosts
  return hosts
end

opts :get_network_ref_by_name do
  summary "Get all vm networks"
  arg :dc, nil, :lookup => VIM::Datacenter
  arg :name, nil, :type => :string
end

def get_network_ref_by_name dc,name
  for network in dc.network
    if name == network.name
      puts network._ref
      return
    end
  end
  puts "NOT FOUND"
end

opts :get_network_type_by_name do
  summary "Get all vm networks"
  arg :dc, nil, :lookup => VIM::Datacenter
  arg :name, nil, :type => :string
end

def get_network_type_by_name dc,name,
  found = false
  network_type = ""
  for network in dc.network
    if name == network.name
      found = true
      network_type = network.class
      break
    end
  end

  if !found
    puts "NOT FOUND!"
  else
    puts network_type
  end
end

opts :has_duplicate_network_name do
  summary "check if has duplicate network name"
  arg :cluster, nil, :lookup => VIM::ComputeResource
  arg :name, nil, :type => :string
end

def has_duplicate_network_name cluster, name,
  dc = cluster.parent.parent
  while ! dc.is_a? VIM::Datacenter
    dc = dc.parent
  end
  found = false
  networks = []
  for network in dc.network
    if name == network.name and !(network.host & cluster.host).empty?#found
      path = []
      found = true
      while network.parent.is_a? VIM::Folder
        path << network.name
        network = network.parent
      end
      networks << path
      # break
    end
  end
  if !found
    puts "NOT FOUND!"
  else
    if networks.length > 1
      puts true
    else
      puts false
    end
  end
end

opts :get_network_by_name do
  summary "Get all vm networks"
  arg :dc, nil, :lookup => VIM::Datacenter
  arg :name, nil, :type => :string
end

def get_network_by_name dc,name,
  found = false
  networks = []
  for network in dc.network
    if name == network.name
      path = []
      found = true
      while network.parent.is_a? VIM::Folder
        path << network.name
        network = network.parent
      end
      networks << path
      # break
    end
  end
  if !found
    puts "NOT FOUND!"
  else
    networks.each do |network|
      nw_path = "networks"
      path = network.reverse
      for i in path
        nw_path = nw_path+"/"+i
      end
      puts "#{nw_path}"
    end
  end
end

opts :get_network_instance_by_name do
  summary "Get all vm networks"
  arg :cluster, nil, :lookup => VIM::ComputeResource
  arg :name, nil, :type => :string
end

def get_network_instance_by_name cluster,name,
  found = false
  path = []
  nw_path = "networks"
  for network in cluster.network
    if name == network.name
      found = true
      $shell.fs.marks['dest_network'] = [network];
      break
    end
  end
end
opts :get_current_time do
  summary "get vCenter time from cluster"
  arg :cluster, nil, :lookup => VIM::ComputeResource
end

def get_current_time cluster
  return [cluster._connection.serviceInstance.CurrentTime,cluster]
end

opts :get_current_time_by_path do
  summary "need to have clusterpath set as string as pre-req"
end

def get_current_time_by_path
  cur_time = []
  $clusterpath.each do |clusterpath|
    cl_path_escape = Shellwords.escape("#{clusterpath}")
    params = ["vsantest.perf.get_current_time","#{cl_path_escape}"]
    if cur_time.empty?
      cur_time = $shell.eval_command(params.join(" "))
    else
      cur_time << $shell.eval_command(params.join(" "))[1]
    end
  end
  puts cur_time
  return cur_time
end

opts :vsan_perf_diagnose do
  summary "Deploys VMs needed for the test"
  arg :cluster, nil, :lookup => VIM::ComputeResource
  arg :queryType, "eval, iops, lat, tput", :default => "iops", :type => :string
  arg :path, "output file path",:default => "/tmp",:type => :string
  arg :duration_sec, "duration in seconds", :default => 3600, :type => :integer
end

def vsan_perf_diagnose cluster, queryType, path, duration_sec
  conn = cluster._connection
  et = conn.serviceInstance.CurrentTime
  st = et - duration_sec.to_i
  et = et.to_datetime
  st = st.to_datetime
  if _save_time_range(cluster, st, et, st.to_s)
    perf_diag_result = _vsan_perf_diagnose(cluster, queryType, st, et)
    if perf_diag_result and perf_diag_result != []
      vsan_disk_map = get_vsan_disks_info(cluster)
      detail_dict = get_supported_diag_exceptions(cluster)
      exception_dgs = {}
      exception_rec = {}
      dg_labels = {}
      for entry in perf_diag_result
        item = YAML.load(entry.to_yaml.gsub(/!ruby\S*$/,""))
        exceptionId = item["props"][:exceptionId]
        recommendation = item["props"][:recommendation]
        #Assuming each exceptionId has only one recommendation
        if not exception_rec.has_key?(exceptionId)
          exception_rec[exceptionId] = recommendation
        end
        #Add exception id into the hash as key if not added
        if not exception_dgs.has_key?(exceptionId)
          exception_dgs[exceptionId] = []
          dg_labels = {}
        end

        if item["props"][:aggregationData]
          dg = item["props"][:aggregationData]["props"][:entityRefId]

          if not dg_labels.has_key?(dg)
            dg_labels[dg] = []
          end

          for item_agData in item["props"][:aggregationData]["props"][:value]
            label = item_agData["props"][:metricId]["props"][:label]
            direction = item_agData["props"][:threshold]["props"][:direction]
            threshold = item_agData["props"][:threshold]["props"][:yellow]
            dg_labels[dg] << {"lable" => label, "direction" => direction, "threshold" => threshold}
          end
        else
          for index_data in item["props"][:exceptionData]
            dg = index_data["props"][:entityRefId]
            dg_labels[dg] = [] if not dg_labels.has_key?(dg)

            for index_label in index_data["props"][:value]
              label = index_label["props"][:metricId]["props"][:label]
              direction = index_label["props"][:threshold]["props"][:direction]
              threshold = index_label["props"][:threshold]["props"][:yellow]
              dg_labels[dg] << {"lable" => label, "direction" => direction, "threshold" => threshold}
            end
          end
        end
        exception_dgs[exceptionId] = dg_labels
      end

      for exceptionId in exception_dgs.keys
        puts "Issue Name: #{detail_dict[exceptionId][0]}"
        puts "Issue Device(s):"
        for entityId in exception_dgs[exceptionId].keys
          deviceMsg = "#{entityId}"
          if entityId.include? "capacity-disk:"
            deviceMsg = "Capacity Disk #{vsan_disk_map[entityId.gsub(/capacity-disk:/,'')]['displayName']} in host #{vsan_disk_map[entityId.gsub(/capacity-disk:/,'')]['host']}"
          elsif entityId.include? "disk-group:"
            deviceMsg = "Disk Groups which is using #{vsan_disk_map[entityId.gsub(/disk-group:/,'')]['displayName']} as cache tier in host #{vsan_disk_map[entityId.gsub(/disk-group:/,'')]['host']}"
          end
          puts "#{deviceMsg}"
          for map in exception_dgs[exceptionId][entityId]
            puts "Detals: #{map['lable']} is #{map['direction']} than threshold #{map['threshold']}"
          end
        end
        puts "Issue Description: #{detail_dict[exceptionId][1]}"
        puts "Issue KB: #{detail_dict[exceptionId][2]}"
        puts "=========================================================="
      end

      `rm -rf "#{path}/#{queryType}_result.yaml"`
      open("#{path}/#{queryType}_result.yaml", 'a') { |f|
        f.puts perf_diag_result.to_yaml.gsub(/!ruby\S*$/,"")
      }

      open("#{path}/#{queryType}_result.txt", 'a') { |f|
        for exceptionId in exception_dgs.keys
          f.puts "Issue Name: #{detail_dict[exceptionId][0]}"
          f.puts "Issue Device(s):"
          for entityId in exception_dgs[exceptionId].keys
            deviceMsg = "#{entityId}"
            if entityId.include? "capacity-disk:"
              deviceMsg = "Capacity Disk #{vsan_disk_map[entityId.gsub(/capacity-disk:/,'')]['displayName']} in host #{vsan_disk_map[entityId.gsub(/capacity-disk:/,'')]['host']}"
            elsif entityId.include? "disk-group:"
              deviceMsg = "Disk Groups which is using #{vsan_disk_map[entityId.gsub(/disk-group:/,'')]['displayName']} as cache tier in host #{vsan_disk_map[entityId.gsub(/disk-group:/,'')]['host']}"
            end
            f.puts "#{deviceMsg}"
            for map in exception_dgs[exceptionId][entityId]
              f.puts "Detals: #{map['lable']} is #{map['direction']} than threshold #{map['threshold']}"
            end
          end
          f.puts "Issue Description: #{detail_dict[exceptionId][1]}"
          f.puts "Issue KB: #{detail_dict[exceptionId][2]}"
          f.puts "=========================================================="
        end
      }
    elsif perf_diag_result == []
      puts "results is empty"
    end
  end
end

opts :get_supported_diag_exceptions do
  summary "get exceptions dictionary"
  arg :cluster, nil, :lookup => VIM::ComputeResource
end

def get_supported_diag_exceptions cluster
  conn = cluster._connection
  vsan = conn.vsan
  vpm = vsan.vsanPerformanceManager
  results = vpm.VsanPerfGetSupportedDiagnosticExceptions()
  dict = {}
  for entry in results
    item = YAML.load(entry.to_yaml.gsub(/!ruby\S*$/,""))
    dict[item["props"][:exceptionId]] = [item["props"][:exceptionMessage],item["props"][:exceptionDetails],item["props"][:exceptionUrl]]
  end
  return dict
end

opts :get_vsan_disks_info do
  summary "show host, drive name, model of vsan disks"
  arg :cluster, nil, :lookup => VIM::ComputeResource
end

def get_vsan_disks_info cluster
  disk_info_map = {}
  hosts = cluster.host
  for hostd in hosts
    for disk in hostd.configManager.vsanSystem.QueryDisksForVsan
      if disk.vsanUuid != ""
        disk_info_map[disk.vsanUuid] = {"host" => hostd.name, "Model" => disk.disk.model, "displayName" => disk.disk.displayName}
      end
    end
  end
  return disk_info_map
end

def _get_cluster_name cluster
  return cluster.name
end

def _get_vc_uuid cluster
  conn = cluster._connection
  vcuuid =  conn.instanceUuid
  return vcuuid
end

def _get_vc_version cluster
  conn = cluster._connection
  version = conn.serviceContent.about.version.to_f
  build_num = conn.serviceContent.about.build.to_i
  return [version,build_num]
end

opts :vsan_cluster_perf_service_enabled do
  summary "query time range from vsan perf service"
  arg :cluster, nil, :lookup => VIM::ComputeResource
end

def vsan_cluster_perf_service_enabled cluster
  if _query_time_range(cluster)
    puts "True"
  else
    puts "False"
  end
end

opts :vsan_cluster_perfsvc_switch_verbose do
  summary "Switch on/off verbose mode"
  arg :cluster, nil, :lookup => VIM::ComputeResource
  arg :verbose_mode, "Switch verbose mode on/off", :default => false, :type => :boolean
end

def vsan_cluster_perfsvc_switch_verbose cluster,verbose_mode
  conn = cluster._connection
  vsan = conn.vsan
  begin
    vpm = vsan.vsanPerformanceManager
    vpm.VsanPerfToggleVerboseMode(
      :cluster => cluster,
      :verboseMode => verbose_mode
      )
  rescue Exception => ex
    puts ex
  end
end

def _query_time_range cluster
  conn = cluster._connection
  vsan = conn.vsan
  begin
    vpm = vsan.vsanPerformanceManager
    querySpec = VIM::VsanPerfTimeRangeQuerySpec()
    vpm.VsanPerfQueryTimeRanges(
      :cluster => cluster,
      :querySpec => querySpec
      )
  rescue Exception => ex
    return false
  end
  return true
end

def _save_time_range cluster, startTime, endTime, timeRangeName
  conn = cluster._connection
  vsan = conn.vsan
  vpm = vsan.vsanPerformanceManager
  timeRange = VIM::VsanPerfTimeRange(
    :endTime => endTime,
    :startTime => startTime,
    :name => timeRangeName
    )
  begin
    vpm.VsanPerfSaveTimeRanges(
      :cluster => cluster,
      :timeRanges => [timeRange]
      )
  rescue Exception => ex
    puts ex
            #puts "saveTimeRange method not found, you need to have vCenter 6.5 update 1 and turn on vSAN Performance Service to make it available"
            return false
          end
          return true
        end

#opts :vsan_perf_output do
#  summary "perf output"
#  arg :cluster, nil, :lookup => VIM::ComputeResource
#  arg :stime, "start time in utc", :lookup => VIM::DateTime
#  arg :etime, "end time in utc", :lookup => VIM::DateTime
#end
def vsan_perf_output cluster, stime, etime
  conn = cluster._connection
  vsan = conn.vsan
  et = etime
  st = stime
  domclientuuid = cluster.configurationEx.vsanConfigInfo.defaultConfig.uuid
  vpm = vsan.vsanPerformanceManager
  vpq = VIM::VsanPerfQuerySpec(
    :entityRefId => "cluster-domclient:#{domclientuuid}",
    :startTime => st,
    :endTime => et,
    :interval => 600
    )
  begin
    perf_diag = vpm.VsanPerfQueryPerf(
      :cluster => cluster,
      :querySpecs => [vpq]
      )
  rescue Exception => ex
    puts ex
    puts "vsanPerfDiag method not found"
    return
  end
  for entry in perf_diag
    item = YAML.load(entry.to_yaml.gsub(/!ruby\S*$/,""))["props"]
    puts "Time Samples: #{item[:sampleInfo]}"
    for val in item[:value]
      puts "#{val["props"][:metricId]["props"][:label]}: #{val["props"][:values]}"
    end
  end
end

def _get_workload_params file_name
  # default values
  puts "Reading HCIBench config file /opt/automation/conf/perf-conf.yaml"
  entry = YAML.load_file("/opt/automation/conf/perf-conf.yaml")
  numvms = entry["number_vm"]
  dropcache = entry["clear_cache"]
  sizedisks = entry["size_data_disk"]
  tool = entry["tool"]

  workload = { "benchmark" => "hcibench/#{tool}"}
  workload["size"] = sizedisks.to_s+"GB"
  workload["vms"] = numvms
  workload["dropcache"] = dropcache
  oio = 0
  numdisks = 0
  temp_workload = {}

  puts "Reading from file:"
  puts file_name
  begin
    if tool == "vdbench"
      File.readlines(file_name).each do |line|
        lineType = "unknown"
        values = line.split(",")
        values.each do |value|
          pairs = value.split("=")
          if lineType == "unknown"
            if pairs[0] == "sd"
              lineType = "sd"
              numdisks += 1
            elsif pairs[0] == "wd"
              lineType = "wd"
            elsif pairs[0] == "rd"
              lineType = "rd"
            end
          end
          if lineType == "sd"
            if pairs[0] == "threads"
              oio += pairs[1].to_i
            else
              oio += 8
            end
          elsif lineType == "wd"
            if pairs[0] == "xfersize"
              workload["iosize"] = pairs[1]
            elsif pairs[0] == "rdpct"
              workload["rdpct"] = pairs[1].to_i
            elsif pairs[0] == "seekpct"
              workload["seekpct"] = pairs[1].to_i
            end
          elsif lineType == "rd"
            if pairs[0] == "iorate"
              workload["iorate"] = pairs[1]
            elsif pairs[0] == "elapsed"
              workload["duration"] = pairs[1].to_i
            end
          end
        end
      end
    elsif tool == "fio"
      temp_workload["filename"] = 0
      temp_workload["iodepth"] = 0
      temp_workload["size"] = 0
      File.readlines(file_name).each do |line|
        if line.include? "="
          k, v = line.split('=', 2)
          case k
          when "readwrite","percentage_random","rwmixread"
            temp_workload[k] = v
          when "runtime"
            workload["duration"] = v.to_i
          when "blocksize"
            workload["iosize"] = v.strip
          when "rate_iops"
            workload["iorate"] = v.to_i
          when "filename"
            temp_workload[k] += 1
          when "iodepth"
            temp_workload[k] += v.to_i
          when "size"
            temp_workload[k] += (v.to_f)/100
          end
        end  
      end    
      if temp_workload.has_key? "percentage_random"
        workload['seekpct'] = temp_workload["percentage_random"].to_i
      elsif temp_workload["readwrite"].include? "rand"
        workload['seekpct'] = 100
      else
        workload['seekpct'] = 0
      end
      if temp_workload.has_key? "rwmixread"
        workload["rdpct"] = temp_workload["rwmixread"].to_i
      elsif temp_workload["readwrite"].include? "read"
        workload["rdpct"] = 100
      else
        workload["rdpct"] = 0
      end

      oio = temp_workload["iodepth"]
      numdisks = temp_workload["filename"]
      avg_pct = temp_workload["size"].to_f/temp_workload["filename"].to_f
      workload["wss"] = (sizedisks.to_f*avg_pct).to_s + "GB"
    end
    workload["oio"] = oio
    workload["numdisks"] = numdisks

  rescue Exception => ex
    puts ex
    puts "Error in opening parameter file"
    return
  end
  p workload
  return workload
end

def _vsan_perf_diagnose cluster, queryType, startTime, endTime, file_name = ''
  version = _get_vc_version(cluster)[0].to_f
  conn = cluster._connection
  vsan = conn.vsan
  vpm = vsan.vsanPerformanceManager
  pdq = VIM::VsanPerfDiagnoseQuerySpec(
    :endTime => endTime,
    :startTime => startTime,
    :queryType => queryType
    )

  if version >= 6.7 and file_name != ''
    pdq = VIM::VsanPerfDiagnoseQuerySpec(
      :endTime => endTime,
      :startTime => startTime,
      :queryType => queryType,
      :context => _get_workload_params(file_name).to_json
      )
  end
  p pdq
  begin
    perf_diag = vpm.VsanPerfDiagnose(
      :cluster => cluster,
      :perfDiagnoseQuery => pdq
      )
  rescue Exception => ex
    puts ex
    puts "vsanPerfDiag method not found, you need to have vCenter 6.5 update 1 and turn on Customer Experience Improvement Program and vSAN Performance Service to make it available"
    return
  end
  return perf_diag
end

opts :deploy_tvm do
  summary "Deploys VMs needed for the test"
  arg :cluster, nil, :lookup => VIM::ComputeResource
  opt :network, "Destination network (used for all vNics)", :lookup => VIM::Network, :required => true, :type => :string
  opt :datastore, "If not specified, VSAN is used", :lookup => VIM::Datastore
  opt :no_thin, "Don't use thin provisioning", :default => false, :type => :boolean
  opt :name_prefix, "Name prefix", :default => "hci-tvm"
  opt :num_vms, "number of VMs to deploy", :default => 10, :type => :integer
  opt :static, "use dhcp or static ip", :default => false, :type => :boolean
  opt :ip, "starting ip address assigned to the vm", :type => :string
  opt :ip_size, "network size used by the vm", :type => :integer
  opt :host, "specify the host name/ip to deploy on and clone to itself", :type => :string
  opt :resource_pool, "specify the name of the resource pool in the cluster", :type => :string
  opt :vm_folder, "specify the root vm folder the vms will be deployed on initially", :type => :string
end

def deploy_tvm cluster, opts
  url = 'http://localhost/vm-template/tvm/tvm.ovf'
  ovf_uri = URI.parse url
  ovf_str = open(ovf_uri, 'r').read
  ovf_xml = Nokogiri::XML(ovf_str).remove_namespaces!
  ovf_networks = Hash[ovf_xml.xpath('//NetworkSection/Network').map do |x|
    desc = x.xpath('Description').first
    [x['name'], desc ? desc : '']
  end]

  network_mappings = Hash[ovf_networks.keys.map{|x| [x, opts[:network]]}]
  puts "networks: #{network_mappings.map{|k, v| k + ' = ' + v.name}.join(', ')}"

  property_mappings = {}
  conn = cluster._connection
  isHostd = (conn.serviceContent.about.apiType == "HostAgent")
  dc = cluster.parent.parent
  while ! dc.is_a? VIM::Datacenter
    dc = dc.parent
  end

  datastore = opts[:datastore]
  folder = dc.vmFolder
  hosts = cluster.host
  vms = []

  cluster_rp = cluster.resourcePool
  cluster_folder = folder

  if opts[:resource_pool] and opts[:resource_pool] != ""
    if cluster.resourcePool.resourcePool.any?
      cluster.resourcePool.resourcePool.each do |rp|
        if rp.name == opts[:resource_pool]
          cluster_rp = rp
        end
      end
    end
  end

  if opts[:vm_folder] and opts[:vm_folder] != ""
    if folder.childEntity.any?
      folder.childEntity.each do |fd|
        if fd.name == opts[:vm_folder]
          cluster_folder = fd
        end
      end
    end
  end

  if isHostd
    begin
      vm = conn.serviceContent.ovfManager.deployOVF(
        :uri => ovf_uri,
        :vmName => "#{opts[:name_prefix]}-1",
        :vmFolder => cluster_folder,
        :host => hosts[0],
        :resourcePool => cluster_rp,
        :datastore => datastore,
        :networkMappings => network_mappings,
        :propertyMappings => property_mappings
        )
      vms << vm
    rescue Exception => ex
      puts ex
      puts "Deploy Error:"
      puts 255
      exit(255)
    end
  else
    host_to_deploy = nil
    if opts[:host] and opts[:host] != ""
      hosts.each do |host|
        if opts[:host] == host.name or opts[:host] == IPSocket.getaddress(host.name)
          host_to_deploy = host
          break
        end
      end
      if !host_to_deploy
        puts "Did not find #{opts[:host]} in the cluster, will deploy and clone VMs across the cluster"
      end
    end

    batch_num = opts[:name_prefix][-1].to_i
    host_num = batch_num % hosts.length

    host = host_to_deploy || hosts[host_num]
    puts "Deploying VM on #{host.name}..."

    #if system("ping -c 2 #{host.name}") and system("timeout 3 bash -c 'cat < /dev/null > /dev/tcp/#{host.summary.managementServerIp}/443'")
    if host.summary.runtime.connectionState == "connected"

      begin
        vm = conn.serviceContent.ovfManager.deployOVF(
          :uri => ovf_uri,
          :vmName => "#{opts[:name_prefix]}-1",
          :vmFolder => cluster_folder,
          :host => host,
          :resourcePool => cluster_rp,
          :datastore => datastore,
          :networkMappings => network_mappings,
          :propertyMappings => property_mappings
          )
      rescue Exception => ex
        puts ex
        puts "Deploy Error:"
        puts 255
        exit(255)
      end
    else
      puts "Can't connect host #{host.name}"
      puts 255
      exit(255)
    end
    vms << vm
  end
  vms = vms.compact

  #for ACI Switch, will need guest ping the controller in order to activate the ip.
  if opts[:static]

    controller_ip = `ip a show dev eth1 | grep global | awk {'print $2'} | cut -d "/" -f1`.chomp
    vms.each do |vm|
      hash = {"guestinfo.vlan_static"=>"true", "guestinfo.vlan_ip"=>opts[:ip], "guestinfo.vlan_size"=>opts[:ip_size].to_s, "guestinfo.controller_ip"=>controller_ip}
      cfg = {
        :extraConfig => hash.map { |k,v| { :key => k, :value => v } },
      }
      vm.ReconfigVM_Task(:spec => cfg).wait_for_completion
    end
  end

  puts "Powering on VMs ..."
  tasks = vms.map{|x| x.PowerOnVM_Task}
  progress(tasks)

  puts "Waiting for VMs to boot ..."
  $shell.fs.marks['tvms'] = vms
  sleep(60)

  vms.each do |vm|
    check_retry = 0
    puts vm.guestHeartbeatStatus
    while ["grey", "red"].include?(vm.guestHeartbeatStatus)
      if check_retry == 3
        $shell.eval_command("vm.kill ~tvms")
        puts "VM guest status is #{vm.guestHeartbeatStatus}, please check the ESXi and the connection between HCIBench and ESXi: #{host.name} port 443"
        puts "255"
        exit(255)
      else
        sleep(2)
        check_retry = check_retry + 1
      end
    end
  end

  begin
    Timeout::timeout(120) do
      $shell.eval_command("vm.ip ~tvms")
    end
  rescue Timeout::Error => e
    puts e
    $shell.eval_command("vm.kill ~tvms")
    puts "VM does not get ip"
    puts 254
    exit(254)
  end
  sleep(30)
  vms.each do |vm|
    vm_ip = vm.getipAddress
    `sed -i '/#{vm_ip} /d' /root/.ssh/known_hosts`
    time_retry = 0
    while not system("ping -c 5 #{vm_ip}")
      sleep(60)
      time_retry = time_retry + 1
      if time_retry == 5
        $shell.eval_command("vm.kill ~tvms")
        puts "Can't Ping VM #{vm} by IP #{vm_ip}"
        puts 254
        exit(254)
      end
    end

    if not system("sshpass -p 'VMware1!' ssh -o 'StrictHostKeyChecking=no' #{vm_ip} 'exit'")
      `> /root/.ssh/known_hosts`
      $shell.eval_command("vm.kill ~tvms")
      puts "Can't SSH to VM #{vm} by IP #{vm_ip}"
      puts 253
      exit(253)
    end
  end
  `> /root/.ssh/known_hosts`
end

opts :deploy_test_vms do
  summary "Deploys VMs needed for the test"
  arg :cluster, nil, :lookup => VIM::ComputeResource
  opt :network, "Destination network (used for all vNics)", :lookup => VIM::Network, :required => true, :type => :string
  opt :datastore, "If not specified, VSAN is used", :lookup => VIM::Datastore
  opt :datadisk_size_gb, "Size of data disk", :default => 10, :type => :integer
  opt :datadisk_num, "Number of data disks", :default => 10, :type => :integer
  opt :no_thin, "Don't use thin provisioning", :default => false, :type => :boolean
  opt :create_only, "Just create VMs, no prep for tests"
  opt :name_prefix, "Name prefix", :default => "vdbench-perf"
  opt :num_vms, "number of VMs to deploy", :default => 10, :type => :integer
  opt :static, "use dhcp or static ip", :default => false, :type => :boolean
  opt :ip, "starting ip addresses assigned to the vms", :type => :string, :multi => true
  opt :ip_size, "network size used by the vm", :type => :integer
  opt :storage_policy, "the name of policy", :type => :string
  opt :host, "specify the host name/ip to deploy on and clone to itself", :type => :string, :multi => true
  opt :resource_pool, "specify the name of the resource pool in the cluster", :type => :string
  opt :vm_folder, "specify the root vm folder the vms will be deployed on initially", :type => :string
  opt :tool, "Specify the tool will be used for testing", :default => "vdbench", :type => :string
  opt :num_cpu, "number of CPU to configure per VM", :default => 4, :type => :integer
  opt :size_ram, "size of RAM to configure per VM in GB", :default => 8, :type => :integer
  opt :multi_writer, "whether to deploy multi-writer disks", :default => false, :type => :boolean
  opt :ctrlr_type, "vController type, pvscsi or nvme", :default => "pvscsi", :type => :string
end

def deploy_test_vms cluster, opts
  url = 'http://localhost/vm-template/perf-photon-hcibench.ovf'
  ovf_uri = URI.parse url
  ovf_str = open(ovf_uri, 'r').read
  ovf_xml = Nokogiri::XML(ovf_str).remove_namespaces!
  ovf_networks = Hash[ovf_xml.xpath('//NetworkSection/Network').map do |x|
    desc = x.xpath('Description').first
    [x['name'], desc ? desc : '']
  end]

  network_mappings = Hash[ovf_networks.keys.map{|x| [x, opts[:network]]}]
  puts "networks: #{network_mappings.map{|k, v| k + ' = ' + v.name}.join(', ')}"

  property_mappings = {}
  conn = cluster._connection
  isHostd = (conn.serviceContent.about.apiType == "HostAgent")
  dc = cluster.parent.parent
  while ! dc.is_a? VIM::Datacenter
    dc = dc.parent
  end

  if opts[:datastore]
    datastore = opts[:datastore]
  else
    datastore = dc.datastore.find do |x|
      x.class.to_s == "Datastore" and x.summary.type == "vsan" and x.host[0].key.parent == cluster
    end
  end
  folder = dc.vmFolder
  hosts = cluster.host
  vms = []

  cluster_rp = cluster.resourcePool
  cluster_folder = folder

  if opts[:resource_pool] and opts[:resource_pool] != ""
    if cluster.resourcePool.resourcePool.any?
      cluster.resourcePool.resourcePool.each do |rp|
        if rp.name == opts[:resource_pool]
          cluster_rp = rp
        end
      end
    end
  end

  if opts[:vm_folder] and opts[:vm_folder] != ""
    if folder.childEntity.any?
      folder.childEntity.each do |fd|
        if fd.name == opts[:vm_folder]
          cluster_folder = fd
        end
      end
    end
  end
  vmProfile = nil
  if opts[:storage_policy] != ""
    vmProfile = [VIM::VirtualMachineDefinedProfileSpec(:profileId => get_policy_id_by_name(dc,opts[:storage_policy]))]
  end
  puts "#{cluster.host[0].name}"
  cpu_num = opts[:num_cpu] || 4
  ram_num = opts[:size_ram] * 1024 || 8 * 1024
  if isHostd
    (1..opts[:num_vms]).map do |idx|
      Thread.new do
        begin
          puts "#{opts[:name_prefix]}-#{idx}"
          vm = conn.serviceContent.ovfManager.deployOVF(
            :uri => ovf_uri,
            :vmName => "#{opts[:name_prefix]}-#{idx}",
            :vmFolder => cluster_folder,
            :host => hosts[0],
            :resourcePool => cluster_rp,
            :datastore => datastore,
            :networkMappings => network_mappings,
            :propertyMappings => property_mappings
#            :defaultProfile => vmProfile
            )
          vm.UpgradeVM_Task
          $shell.fs.marks['vm_to_add_cpu'] = vm;
          $shell.eval_command("vm.modify_cpu -n #{cpu_num} ~vm_to_add_cpu")
          $shell.eval_command("vm.modify_memory -s #{ram_num} ~vm_to_add_cpu")
          add_data_disk([vm],
            :no_thin => opts[:no_thin],
            :size_gb => opts[:datadisk_size_gb],
            :num => opts[:datadisk_num],
            :add_ctrlr => true,
            :ctrlr_type => opts[:ctrlr_type],
            :profile_id => opts[:storage_policy]? get_policy_id_by_name(vm,opts[:storage_policy]) : ""
            ) if not opts[:multi_writer]
          vms << vm
        rescue Exception => ex
          pp [ex.class, ex.message]
        end
      end
    end.each{|t| t.join}
  else
    host_to_deploy = []
    if opts[:host] and opts[:host] != []
      opts[:host].each do |host_name|
        hosts.each do |host|
          puts host.name
          puts host_name
          if host_name == host.name or host_name == IPSocket.getaddress(host.name)
            host_to_deploy << host
          end
        end
      end
      if host_to_deploy == []
        puts "Did not find #{opts[:host]} in the cluster, will deploy and clone VMs across the cluster"
      end
    end
    hosts = host_to_deploy if host_to_deploy != []
    batch_num = opts[:name_prefix][-1].to_i
    host_num = batch_num % hosts.length
    host = hosts[host_num]

    if host.summary.runtime.connectionState == "connected"
      begin
        vm = conn.serviceContent.ovfManager.deployOVF(
          :uri => ovf_uri,
          :vmName => "#{opts[:name_prefix]}-1",
          :vmFolder => cluster_folder,
          :host => host,
          :resourcePool => cluster_rp,
          :datastore => datastore,
          :networkMappings => network_mappings,
          :propertyMappings => property_mappings,
          :defaultProfile => vmProfile
          )
        vm.UpgradeVM_Task
        $shell.fs.marks['vm_to_add_cpu'] = vm;
        $shell.eval_command("vm.modify_cpu -n #{cpu_num} ~vm_to_add_cpu")
        $shell.eval_command("vm.modify_memory -s #{ram_num} ~vm_to_add_cpu")
        add_data_disk([vm],
          :no_thin => opts[:no_thin],
          :size_gb => opts[:datadisk_size_gb],
          :num => opts[:datadisk_num],
          :add_ctrlr => true,
          :ctrlr_type => opts[:ctrlr_type],
          :profile_id => opts[:storage_policy]? get_policy_id_by_name(vm,opts[:storage_policy]) : ""
          ) if not opts[:multi_writer]
        vms << vm
        (1...opts[:num_vms]).each do |i|
          task = vm.CloneVM_Task(:folder => cluster_folder,
           :name => "#{opts[:name_prefix]}-#{i + 1}",
           :spec => {
             :location => {
               :host => hosts[(host_num + i) % hosts.length],
             },
             :template => false,
             :powerOn => false,
           })
          results = progress([task])
          vms += results.values
        end
      rescue Exception => ex
        puts ex
        exit(253)
      end
    else
      puts "Can't connect host #{host.name}"
      exit(255)
    end
  end
  vms = vms.compact
  add_data_disk(vms,
    :no_thin => opts[:no_thin],
    :size_gb => opts[:datadisk_size_gb],
    :num => opts[:datadisk_num],
    :add_ctrlr => true,
    :ctrlr_type => opts[:ctrlr_type],
    :multi_writer => true,
    :profile_id => opts[:storage_policy]? get_policy_id_by_name(vm,opts[:storage_policy]) : ""
    ) if opts[:multi_writer]

  if opts[:create_only]
    return vms
  end

  #for ACI Switch, will need guest ping the controller in order to activate the ip.
  if opts[:static]
    controller_ip = `ip a show dev eth1 | grep global | awk {'print $2'} | cut -d "/" -f1`.chomp
    vms.each_with_index do |vm, index|
      starting_ip = opts[:ip][index]
      hash = {"guestinfo.vlan_static"=>"true", "guestinfo.vlan_ip"=>starting_ip, "guestinfo.vlan_size"=>opts[:ip_size].to_s, "guestinfo.controller_ip"=>controller_ip}
      cfg = {
        :extraConfig => hash.map { |k,v| { :key => k, :value => v } },
      }
      vm.ReconfigVM_Task(:spec => cfg).wait_for_completion
    end
  end

  puts "Powering on VMs ..."
  tasks = vms.map{|x| x.PowerOnVM_Task}
  progress(tasks)

  puts "Waiting for VMs to boot ..."
  $shell.fs.marks['vsantest_perf_vms'] = vms
  begin
    Timeout::timeout(600) do
      $shell.eval_command("vm.ip ~vsantest_perf_vms")
    end
  rescue Timeout::Error => e
    puts e
    p "Can't find all vms' ip, deleting VMs..."
    $shell.eval_command("vm.kill ~vsantest_perf_vms")
    exit(254)
  end

  sleep(30)
  failure_list = []
  vms.each do |vm|
    vm_ip = vm.getipAddress
    time_retry = 1
    while not system("ping -c 5 #{vm_ip}")
      if time_retry == 3
        puts "Can't Ping VM #{vm.name} by IP #{vm_ip}"
        failure_list << vm
        break
      else
        sleep(2)
        time_retry = time_retry + 1
      end
    end
  end

  retry_ping = 1
  while not failure_list.empty?
    puts "Not able to ping VMs #{failure_list.map {|a| a.name}}, try another time..."
    if retry_ping == 15
      puts "Can't Ping VMs #{failure_list.map {|a| a.name}} by their IPs #{failure_list.map {|a| a.getipAddress}}"
      exit(254)
    end
    sleep(60)
    success_list = []
    failure_list.each do |vm|
      vm_ip = vm.getipAddress
      if system("ping -c 5 #{vm_ip}")
        success_list << vm
      end
    end
    failure_list = failure_list - success_list
    retry_ping += 1
  end

  puts "Post Checking VM Config"
  vms.each do |vm|
    check_retry = 0
    while true
      disk_num = vm.post_check
      if disk_num < opts[:datadisk_num].to_i and check_retry < 3
        vm_arr = [vm]
        add_data_disk(vm_arr,
          :no_thin => opts[:no_thin],
          :size_gb => opts[:datadisk_size_gb],
          :num => (opts[:datadisk_num].to_i-disk_num),
          :add_ctrlr => false,
          :ctrlr_type => opts[:ctrlr_type],
          :profile_id => opts[:storage_policy]? get_policy_id_by_name(vm,opts[:storage_policy]) : ""
          )
      elsif check_retry == 3
        puts "Unable to add disk to VM"
        exit(252)
      else
        break
      end
    end
  end

  if opts[:tool] == "vdbench"
    puts "Configuring vdbench"
    install_vdbench(vms)
  end
  puts "Configuring fio"
  install_fio(vms)
  puts "Uploading graphite scripts"
  install_scripts(vms)
  puts "Installing diskinit"
  install_diskinit(vms)
  puts "VMs ready for perf runs ..."
  vms
end

opts :run_observer do
  summary "Deploys VMs needed for the test"
  arg :vcip, nil, :type => :string
  arg :path, nil, :type => :string
  arg :name, nil, :type => :string
end

def run_observer vcip, path, name
  FileUtils.mkdir_p("#{path}/#{name}");
  tracefile = "#{path}/#{name}/observer.trace"
  ob = runObserver(vcip, tracefile);
  an = runAnalyzerThread(tracefile)
  begin
    sleep(10000000)
  ensure
    [ob, an].each do |pid|
      puts "#{Time.now}: Killing pid #{pid}"
      Process.kill("-KILL", Process.getpgid(pid));
    end
    runAnalyzer(tracefile)
  end
end
