# -----------------------------------------------------------------
# -----------------------------------------------------------------
# Internal commands:
# Everything below this line is for VMware internal consumption only
# -----------------------------------------------------------------
# -----------------------------------------------------------------

require 'net/ssh'
require 'net/scp'
require 'base64'

$rvc_vmrc_ver_urls ||= {}
$rvc_vmrc_ver_urls['6.0.0'] = '/vsphere-client/webconsole.html'

def is_uuid str
  str =~ /[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/
end

RbVmomi::VIM::HostSystem

class RbVmomi::VIM::HostSystem
  def _try_ssh_passwords hostname
    $sshPasswords ||= {}
    if $sshPasswords[hostname]
      return $sshPasswords[hostname]
    end
    ['', 'cashc0w'].each do |pw|
      begin
        Net::SSH.start(hostname, "root", :password => pw, :verify_host_key => :never) do |ssh|
          ssh.exec! "uname"
        end
        $sshPasswords[hostname] = pw
        return pw
      rescue
      end
    end
    nil
  end

  def ssh opts = {}
    hostname = self.name
    if !opts[:password]
      opts[:password] = _try_ssh_passwords hostname
    end
    Net::SSH.start(
    hostname, "root",
    :password => opts[:password],
    :verify_host_key => :never) do |ssh|

      yield ssh
    end
  end

  def vsan_disks_capacities opts = {}
    out = {}
    self.ssh(opts) do |ssh|
      disks = ssh.cmmds_find "-t DISK"
      disks_statuses = ssh.cmmds_find "-t DISK_STATUS"
      disks_usages = ssh.cmmds_find "-t DISK_USAGE"

      disks_statuses = Hash[disks_statuses.map{|x| [x['uuid'], x.merge(x['content'])]}]
      disks_usages = Hash[disks_usages.map{|x| [x['uuid'], x.merge(x['content'])]}]

      disks = disks.map do |x|
        x = x.merge(x['content'])
        x['status'] = disks_statuses[x['uuid']]
        x['usage'] = disks_usages[x['uuid']]
        x
      end

      mds = disks.select{|x| x['isSsd'] == 0}
      ssds = disks.select{|x| x['isSsd'] == 1}

      #pp mds

      disks.each do |x|
        out[x['uuid']] = x
      end
    end
    out
  end

  def vsan_disks_capacities_rollup opts = {}
    disks = vsan_disks_capacities opts
    mds = disks.values.select{|x| x['isSsd'] == 0}
    ssds = disks.values.select{|x| x['isSsd'] == 1}

    out = {}
    out['disks_details'] = disks
    out['capacity'] = mds.map{|x| x['capacity']}.inject(0, &:+)
    out['md-capacity-used'] = mds.map{|x| x['status']['capacityUsed']}.inject(0, &:+)
    out['md-capacity-res'] = mds.map{|x| x['usage']['capacityReserved']}.inject(0, &:+)
    out['ssd-capacity'] = ssds.map{|x| x['capacity']}.inject(0, &:+)
    out['ssd-capacity-used'] = ssds.map{|x| x['status']['capacityUsed']}.inject(0, &:+)
    out['ssd-capacity-res'] = ssds.map{|x| x['usage']['capacityReserved']}.inject(0, &:+)
    out['md-iops'] = mds.map{|x| x['iops']}.inject(0, &:+)
    out['ssd-iops'] = ssds.map{|x| x['iops']}.inject(0, &:+)
    out['md-iops-res'] = mds.map{|x| x['usage']['iopsReserved']}.inject(0, &:+)
    out['ssd-iops-res'] = ssds.map{|x| x['usage']['iopsReserved']}.inject(0, &:+)

    # puts "cap = %.2f GB, md-capused = %.2f GB, ssd-space = %.2f GB, ssd-used = %.2f GB" % [
    # out['capacity'].to_f / 1024**3,
    # out['md-capacityused'].to_f / 1024**3,
    # out['ssd-space'].to_f / 1024**3,
    # out['ssd-spaceused'].to_f / 1024**3,
    # ]

    out
  end
end

opts :cluster_disks_stats do
  summary "Show stats on all disks in VSAN"
  arg :clusters, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
  opt :password, "ESX Password", :type => :string
end

def cluster_disks_stats clusters, opts
  conn = clusters.first._connection
  pc = conn.propertyCollector
  clusters_props = pc.collectMultiple(clusters, 'name', 'host')
  # XXX: Would be a good idea to filter the hosts to only include those that
  #      are responsive
  _run_with_rev(conn, "dev") do
    lock = Mutex.new
    disks = Hash[clusters.map{|x| [x, {}]}]
    # In theory we only need to talk to one host out of each CMMDS partition,
    # but heck, lets just get the info from all hosts
    clusters.map do |cluster|
      host = clusters_props[cluster]['host'].first
      Thread.new do
        rollup = host.vsan_disks_capacities_rollup opts
        lock.synchronize do
          disks[cluster] = rollup
        end
      end
    end.each{|x| x.join}

    t = Terminal::Table.new()
    t << [nil,       nil,    'Capacity', nil,   nil,        'Iops', nil]
    t << ['Cluster', 'Type', 'Total',   'Used', 'Reserved', 'Total', 'Reserved']
    t.add_separator
    # XXX: Would be nice to show displayName and host
    clusters.each do |cluster|
      x = disks[cluster]
      t << [
        clusters_props[cluster]['name'],
        'MD',
        "%.2f GB" % [x['capacity'].to_f / 1024**3],
        "%.0f %%" % [x['md-capacity-used'].to_f * 100 / x['capacity'].to_f],
        "%.0f %%" % [x['md-capacity-res'].to_f * 100 / x['capacity'].to_f],
        "%d" % [x['md-iops']],
        "%.0f %%" % [x['md-iops-res'].to_f * 100 / x['md-iops']],
      ]
      t << [
        '',
        'SSD',
        "%.2f GB" % [x['ssd-capacity'].to_f / 1024**3],
        "%.0f %%" % [x['ssd-capacity-used'].to_f * 100 / x['ssd-capacity'].to_f],
        "%.0f %%" % [x['ssd-capacity-res'].to_f * 100 / x['ssd-capacity'].to_f],
        "%d" % [x['ssd-iops']],
        "%.0f %%" % [x['ssd-iops-res'].to_f * 100 / x['ssd-iops']],
      ]
    end

    puts t
  end
end

opts :esxupgrade do
  summary "Upgrade ESX boxes"
  arg :host, nil, :lookup => [VIM::HostSystem], :multi => true
  opt :build, "ESX build", :type => :string, :required => true
  opt :password, "ESX Password", :type => :string
  opt :force, "Apply the force", :type => :boolean
end

def esxupgrade hosts, opts
  conn = hosts.first._connection
  pc = conn.propertyCollector
  depot = "http://build-squid.eng.vmware.com/build/mts/release/bora-#{opts[:build]}/publish/CUR-depot/ESXi/index.xml"
  if opts[:build] =~ /sb-(.*)/
    opts[:build] = $1
    depot = "http://build-squid.eng.vmware.com/build/mts/release/sb-#{opts[:build]}/publish/CUR-depot/ESXi/index.xml"

  end
  hosts_props = pc.collectMultiple(hosts, 'name', 'runtime.connectionState')
  connected_hosts = hosts_props.select do |k,v|
    v['runtime.connectionState'] == 'connected'
  end.keys

  hosts.each do |host|
    host_name = hosts_props[host]['name']
    if !connected_hosts.member?(host)
      puts "Skipping #{host_name} because it is not connected"
    end
  end

  lock = Mutex.new
  threads = hosts.map do |host|
    host_name = hosts_props[host]['name']
    if !connected_hosts.member?(host)
      next
    end
    Thread.new do
      software = host.esxcli.software
      profiles = nil
      host.ssh do |ssh|
        begin
          profiles = software.sources.profile.list(:depot => [depot])
          profile = profiles.find{|x| x.Name =~ /-standard$/}.Name
        rescue
          cmd = "esxcli software sources profile list --depot #{depot}"
          lock.synchronize do
            puts "Running #{cmd.inspect} on host #{host_name}"
          end
          output = ssh.exec! cmd
          line = output.split("\n").find{|x| x =~ /-standard/}
          if !line
            raise "#{host_name}: Couldn't find standard profile in output:\n#{output}"
          end
          profile = line.split(/[ \t]/).first
        end
        cmd = "esxcli software profile update"
        cmd += " --depot #{depot} --profile #{profile} --no-sig-check"
        if opts[:force]
          cmd += " --force --allow-downgrades"
        end
        lock.synchronize do
          puts "Running #{cmd.inspect} on host #{host_name}"
        end
        output = ssh.exec! cmd
        lock.synchronize do
          puts "Host #{host_name} returned:"
          puts output
          puts
        end
      end
    end
  end.compact
  threads.each{|t| t.join}
end

opts :dom_owner_latencies do
  summary "Ownerstats"
  arg :host, nil, :lookup => [VIM::HostSystem], :multi => true
  opt :password, "ESX Password", :type => :string
end

def dom_owner_latencies hosts, opts
  hosts.each do |host|
    host.ssh do |ssh|
      owners_stats = ssh.run_python_file("/vsan-vsi.py", "get_owner_latencies")
      pp owners_stats
      t = Terminal::Table.new()
      t << ['Owner', 'totalMean', 'prepareMean', 'commitMean']
      t.add_separator
      owners_stats.each do |owner, stats|
        t << (
        [owner] +
        ['totalMean', 'prepareMean', 'commitMean'].map do |x|
          "%.2f ms" % [stats[x].to_f / 1000 / 1000]
        end
        )
      end

      puts t
    end
  end
end

opts :dom_owner_stats do
  summary "Ownerstats"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :password, "ESX Password", :type => :string
end

def dom_owner_stats cluster_or_host, opts = {}
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  if cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    hosts = cluster.host
  else
    hosts = [cluster_or_host]
  end

  _run_with_rev(conn, "dev") do
    hosts_props = pc.collectMultiple(hosts,
    'configManager.vsanSystem',
    'name',
    'runtime.connectionState'
    )
    hosts_props = hosts_props.select{|k,v| v['runtime.connectionState'] == 'connected'}
    vsan_systems = hosts_props.map{|h,p| p['configManager.vsanSystem']}
    vsan_props = pc.collectMultiple(vsan_systems, 'config.clusterInfo')
    hostVsanUuids = Hash[hosts_props.map do |host, props|
      vsan_system = props['configManager.vsanSystem']
      vsan_info = vsan_props[vsan_system]['config.clusterInfo']
      [vsan_info.nodeUuid, host]
    end]

    hosts = hosts_props.keys
    host = hosts.first

    host.ssh do |ssh|
      owners_stats = ssh.run_python_file("/vsan-vsi.py", "get_dom_owner_stats")
      t = Terminal::Table.new()
      t << ['Host', 'DOM Owners', 'DOM Owner leafs']
      t.add_separator
      owners_stats.each do |owner, stats|
        host = hostVsanUuids[owner]
        host_name = hosts_props[host]['name']
        t << (
        [host_name, stats['dom_objects_owned'], stats['lsom_objects_owned']]
        )
      end

      puts t
    end
  end
end

opts :continuous_monitoring do
  summary "Starts a continuous monitoring job"
  arg :clusters, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
end

def continuous_monitoring clusters
  require 'rbvmomi/utils/perfdump.rb'

  def run_cron_job minutes
    Thread.new do
      while true
        t1 = Time.now
        yield
        t2 = Time.now
        sleeptime = minutes * 60 - (t2 - t1)
        if sleeptime > 0
          sleep(sleeptime)
        end
      end
    end
  end

  conn = clusters.first._connection
  pc = conn.propertyCollector

  inventory_thread = run_cron_job(5) do
    json = JSON.dump({
      'type' => 'inventory',
      'timestamp' => Time.now.to_i,
      'data' => PerfAggregator.new().collect_info_on_all_vms([conn.rootFolder])
    })
    open('/root/nimbus.vsan.json', 'a'){|io| io.write("#{json}\n")}
  end
  sleep 10
  diagnostics_thread = run_cron_job(5) do
    clusters_props = pc.collectMultiple(clusters, 'host')
    puts "#{Time.now}: Host stats:"
    shell.cmds[:basic].slate.table(
    clusters_props.map{|o,p| p['host']}.flatten,
    :field => [
      'name', 'state.connection',
      'num.vms', 'num.poweredonvms',
      'cpuusage', 'memusage', 'uptime',
      'state.maintenancemode', 'build'
    ],
    :field_given => true
    )
    puts "#{Time.now}: Memory stats:"
    clusters.each do |cluster|
      memory_stats(cluster)
    end
    puts "#{Time.now}: LSOM stats:"
    clusters.each do |cluster|
      lsom_log_stats(cluster)
    end
    puts "#{Time.now}: VSAN physical disk stats:"
    disks_stats(clusters, :compute_number_of_components => true)
    puts "#{Time.now}: VSAN diagnostics:"
    clusters.each do |cluster|
      diagnostics(cluster, :auto_correct => true)
    end
  end

  begin
    diagnostics_thread.join
  rescue Interrupt
    inventory_thread.kill
    diagnostics_thread.kill
  end

end

opts :add_vsan_to_network do
  summary "Add VSAN cluster to a network/DVPortgroup"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource
  arg :portgroup, nil, :lookup => VIM::DistributedVirtualPortgroup
  opt :ips, "Comma separated list of IPs to be used", :type => :string
  opt :netmask, "Subnet mask", :type => :string
end

def add_vsan_to_network cluster, portgroup, opts
  conn = cluster._connection
  ips = (opts[:ips] || "").split(",").select{|x| x && x.length > 0}
  _run_with_rev(conn, "dev") do
    if !cluster.configurationEx.vsanConfigInfo.enabled
      err "Please enable VSAN on the cluster first"
    end
    pg_key = portgroup.key
    dvs = portgroup.config.distributedVirtualSwitch
    dvs_uuid = dvs.uuid

    dvs_hosts = dvs.config.host.map{|x| x.config.host}
    cluster_hosts = cluster.host
    cluster_hosts.each do |host|
      if !dvs_hosts.member?(host)
        err "Host #{host.name} is not member of the DVS #{dvs.name}"
      end
    end

    puts "Adding the vmknics to all hosts ..."
    i = 0
    vmknic_names = cluster_hosts.map do |host|
      ip = {
        :dhcp => true
      }
      if ips[i]
        ip = {
          :dhcp => false,
          :ipAddress => ips[i],
          :subnetMask => opts[:netmask],
        }
      end
      i += 1
      ns = host.configManager.networkSystem
      # XXX: Check if we already have a vmknic connected to this pg and skip if so
      vmknic_name = ns.AddVirtualNic(
      :portgroup => "",
      :nic => {
        :ip => ip,
        :distributedVirtualPort => VIM::DistributedVirtualSwitchPortConnection(
        :portgroupKey => pg_key,
        :switchUuid => dvs_uuid
        )
      }
      )
      [host, vmknic_name]
    end.compact

    puts "Configuring VSAN to consume vmknics ..."
    spec = VIM::ClusterConfigSpecEx(
    :vsanHostConfigSpec => vmknic_names.map do |host, vmknic_name|
      {
        :hostSystem => host,
        :networkInfo => {
        :port => [
        {
        :device => vmknic_name,
        }
        ]
        }
      }
    end
    )
    task = cluster.ReconfigureComputeResource_Task(:spec => spec, :modify => true)
    progress([task])
    progress(task.child_tasks)
  end
end

opts :cluster_free_disks do
  summary "Free a disks on a cluster"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource
  opt :password, "ESX Password", :type => :string
  opt :free_lonely_vmfs, "Delete any VMFS datastore if it the only partition on a disk", :type => :boolean
  opt :free_lonely_coredump, "Delete any coredump partition if it the only partition on a disk", :type => :boolean
end

def cluster_free_disks cluster, opts
  cluster.host.each do |host|
    puts "Host #{host.name}:"
    free_disk host, "*", opts
    puts ""
  end
end

opts :free_disk do
  summary "Free a disk on a host"
  arg :host, nil, :lookup => VIM::HostSystem
  arg :disk, nil, :type => :string
  opt :password, "ESX Password", :type => :string
  opt :free_lonely_vmfs, "Delete any VMFS datastore if it the only partition on a disk", :type => :boolean
  opt :free_lonely_coredump, "Delete any coredump partition if it the only partition on a disk", :type => :boolean
end

def free_disk host, _disk, opts
  conn = host._connection
  pc = conn.propertyCollector
  _run_with_rev(conn, "dev") do
    vsan = host.configManager.vsanSystem
    disks = vsan.QueryDisksForVsan()
    Net::SSH.start(host.name, "root", :password => opts[:password], :verify_host_key => :never) do |ssh|
      disks.each do |disk|
        if _disk != "*"
          if disk.disk.canonicalName == _disk
            next
          end
        end

        dsList = host.datastore
        dsListProps = pc.collectMultiple(dsList, 'summary', 'name', 'info')
        vmfsDsList = dsListProps.select do |ds, props|
          props['summary'].type == "VMFS"
        end.keys

        partitions = host.esxcli.storage.core.device.partition.list
        partitions = partitions.select do |part|
          part.Device == disk.disk.canonicalName
        end
        if disk.state !~ /ineligible/
          puts "Disk #{disk.disk.canonicalName} is not inelgible. Not doing anything to not mess anything up"
          next
        end
        types = {
          0xfb => 'vmfs',
          0xfc => 'coredump',
          0xfa => 'vsan',
          0x0 => 'unused',
          0x6 => 'vfat',
        }
        partitions.each do |part|
          if [7, 222, 11].member?(part.Type)
            cmd = "partedUtil delete /vmfs/devices/disks/#{disk.disk.canonicalName} #{part.Partition}"
            puts "Running #{cmd}"
            puts ssh.exec! cmd
            partitions.remove(part)
          end
        end

        if partitions.all?{|x| x.Type == 0}
          next
        end

        if partitions.all?{|x| types[x.Type] == 'coredump' || x.Type == 0}
          if opts[:free_lonely_coredump]
            puts "Lonely coredump partition detected on #{disk.disk.canonicalName}"
            host.esxcli.system.coredump.partition.set(:unconfigure => true)
            partitions.each do |part|
              if types[part.Type] == 'coredump'
                cmd = "partedUtil delete /vmfs/devices/disks/#{disk.disk.canonicalName} #{part.Partition}"
                puts "Running #{cmd}"
                puts ssh.exec! cmd
              end
            end
          end
        end
        if partitions.all?{|x| types[x.Type] == 'vmfs' || x.Type == 0}
          if opts[:free_lonely_vmfs]
            puts "Lonely vmfs partition detected on #{disk.disk.canonicalName}"
            partitions.select{|x| types[x.Type] == 'vmfs'}.each do |x|
              ds = vmfsDsList.find do |vmfsDs|
                props = dsListProps[vmfsDs]
                props['info'].vmfs.extent.any? do |ext|
                  ext.diskName == x.Device && x.Partition == ext.partition
                end
              end
              if !ds
                puts "Couldn't find a corresponding datastore, deleting partition directly"
                cmd = "partedUtil delete /vmfs/devices/disks/#{disk.disk.canonicalName} #{x.Partition}"
                puts "Running #{cmd}"
                puts ssh.exec! cmd
                next
              end
              vsanClusterUuid = nil
              traceDaemon = nil
              vsan = nil
              begin
                puts "Destroying datastore #{ds.name}"
                ds.Destroy_Task.wait_for_completion
              rescue Exception => ex
                puts "Failed to destroy #{ds.name}: #{ex.class}: #{ex.message}"
                vsan = nil

                cmd = "/etc/init.d/vsantraced status"
                puts "Running #{cmd}"
                out = ssh.exec! cmd
                puts out
                if out =~ /is running/
                  cmd = "/etc/init.d/vsantraced stop"
                  puts "Running #{cmd}"
                  puts ssh.exec! cmd
                  traceDaemon = true
                  retry
                end

                begin
                  vsan = host.esxcli.vsan.cluster.get
                rescue
                end

                if vsan && vsan.SubClusterUUID
                  vsanClusterUuid = vsan.SubClusterUUID
                  puts "Trying to leave VSAN cluster"
                  host.esxcli.vsan.cluster.leave
                  retry
                end
              ensure
                if traceDaemon
                  cmd = "/etc/init.d/vsantraced start"
                  puts "Running #{cmd}"
                  puts ssh.exec! cmd
                end
                if vsanClusterUuid
                  puts "Rejoining the VSAN cluster"
                  host.esxcli.vsan.cluster.join(:"cluster-uuid" => vsanClusterUuid)
                end
              end
            end
          end
        end

        # If any code needs to be added here, we should re-retrieve the partition
        # list
      end
    end
  end
end

class Net::SSH::Connection::Session
  def trace_tail params, num_lines = 50
    trace_dir = "/scratch/vsantraces/"
    trace_file = "#{trace_dir}vsantraces.log.0.gz"
    cmd = "tail -c+0 -f #{trace_file} | zcat | /usr/lib/vmware/vsan/vsanTraceReader.py"
    cmd = "#{cmd} | head -n 5000 #{params} | head -n #{num_lines}"
    out = self.exec! cmd
    out.split("\n").map do |x|
      if x =~ /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{6}) \[(\d+)\] \[pcpu = (\d+)\] \[([\dabcdef]+)\] ([^ ]+):(\d+): (.*)$/
        json = $7
        line = {
          'timestamp' => $1,
          'pcpu' => $3,
          'func' => $5,
          'lineno' => $6,
        }.merge(JSON.load(json.gsub("'", '"').gsub("False", "false")))
      else
        nil
      end
    end.compact
  end

  def lsom_congestion_from_traces
    trace_tail("| grep LSOMCalculateCongestion", 15)
  end

  def dom_delays_from_traces
    trace_tail("| grep DOMFlowctlCongestionDelay", 50).select do |x|
      x['average delay'] != "0:00:00"
    end
  end

  def mem_stats params
    cmd = "memstats #{params} -q "
    out = self.exec! cmd
    lines = out.split("\n")
    lines = lines.map{|x| x.split(",")}
    titles = lines.shift
    lines.map do |line|
      out = {}
      titles.each_with_index do |title, i|
        out[title] = line[i]
      end
      out
    end
  end

  def vsan_mem_group_stats
    entries = self.mem_stats("-r group-stats")

    entries = entries.select do |x|
      name = x['name']
      keep = false
      if name =~ /\./ || name =~ /^(sh|ssh)\./
        next
      end
      keep || ['clomd', 'cmmdsd', 'osfsd', 'vsantraced', 'swapobjd'].member?(x['name'])
    end

    entries
  end

  def vsan_mem_heap_stats
    entries = self.mem_stats("-r heap-stats")

    entries = entries.select do |x|
      name = x['name']
      keep = false
      heaps = %w(
      RDT vsanutil LSOM CMMDSNet CMMDSModule CMMDSChardev
      CMMDSResolver vsan DOM vmfs3 tcpip
      dom-CompServer-heap dom-Owner-heap dom-Client-heap
      )
      if heaps.member?(name)
        keep = true
      end
      keep || ['clomd', 'cmmdsd', 'osfsd'].member?(x['name'])
    end

    entries
  end

  def cmmds_find params
    cmd = "cmmds-tool find --format=json #{params}"
    #puts cmd
    out = self.exec! cmd
    out = JSON.load out
    out['entries']
  end

  def is_uuid str
    str =~ /[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/
  end

  # layoutExs = pc.collectMultiple(vms!, 'layoutEx').values.map{|x| x['layoutEx']}
  # layoutExs.map{|x| x.file.map{|x| x.name}}.flatten.map{|x| if x =~ /^\[([^\]])+\] ([^\/]*)\//; $2; end;}.uniq

  def vsan_find_objects_in_dir dir
    objects = {
      'vmdk' => [],
      'swap' => [],
      'vmem' => [],
      'dirs' => [],
    }

    find_out = self.exec! "find #{dir}"
    if find_out =~ /No such file or directory/ || find_out =~ /Connection timed out/
      puts "#{Time.now}: Warning: Directory #{dir} appears to be inaccessible ... Results will be incomplete"
    end
    find_out = find_out.split("\n")
    vmkds = find_out.select do |x|
      x =~ /\.vmdk$/ && x !~ /-flat\.vmdk$/
    end.each do |file|
      vmdk = self.exec! "cat #{file}"
      if !vmdk
        puts "#{Time.now}: Warning: Failed to print content of #{file}"
        next
      end
      vmdk.split("\n").each do |line|
        if line =~ /^RW (\d+) (VMFS|VMFSSPARSE|VSANSPARSE) "vsan:\/\/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})"$/
          object_uuid = $3
          puts "#{Time.now}: Found #{object_uuid} in #{file}"
          objects['vmdk'] << [object_uuid, file]
        end
      end
    end

    swaps = find_out.select do |x|
      x =~ /\.(vswp|vmem)$/ && x.split('/').last !~ /^vmx-/
    end.each do |file|
      vswp = self.exec! "cat #{file}"
      if !vswp
        puts "#{Time.now}: Warning: Failed to print content of #{file}"
        next
      end
      vswp.split("\n").each do |line|
        if line =~ /^objectID = "vsan:\/\/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})"$/
          object_uuid = $1
          puts "#{Time.now}: Found #{object_uuid} in #{file}"
          if file =~ /\.vswp$/
            objects['swap'] << [object_uuid, file]
          else
            objects['vmem'] << [object_uuid, file]
          end
        end
      end
    end

    objects
  end

  def vsan_find_orphan_objects datastore_name = 'vsanDatastore', dir_list = {}
    ds_path = "/vmfs/volumes/#{datastore_name}/"

    objects = {
      'vmdk' => {},
      'vswp' => {},
      'vmem' => {},
      'dirs' => {},
    }
    leaks = {
      'vmdk' => {},
      'vswp' => {},
      'vmem' => {},
      'dirs' => {},
    }
    puts "#{Time.now}: Querying detailed directory and vmdk/vswp/vmem info from ESX (may take a while)"
    res = self.run_python_file(
    "/vsan-vsi.py",
    "get_directories_info '#{ds_path}'"
    )
    res.each do |dir, dir_objects|
      ufn = dir_objects['ufn'] || dir
      objects['dirs'][ufn] = dir
      if !dir_list.member?(dir)
        leaks['dirs'][ufn] = dir
      end

      objects.keys.each do |key|
        if !dir_objects[key]
          next
        end

        objects[key].merge!(dir_objects[key])
        if !dir_list.member?(dir)
          leaks[key].merge!(dir_objects[key])
        end
      end
    end

    [objects, leaks]
  end

  def vsan_find_orphan_components
    lsom_objects = self.cmmds_find("-t LSOM_OBJECT")
    dom_objects = self.cmmds_find("-t DOM_OBJECT")

    orphans = Hash[lsom_objects.map do |lsom_object|
      [lsom_object['uuid'], lsom_object]
    end]
    dom_objects.each do |dom_object|
      components = _components_in_dom_config dom_object['content']
      components.each do |x|
        orphans.delete(x['componentUuid'])
      end
    end

    orphans
  end

  def cmmds_dom_object obj_uuids
    obj_uuids.reject{|x| is_uuid x}.each do |x|
      puts "Warning: #{x} is not a valid UUID"
    end
    obj_uuids = obj_uuids.select{|x| is_uuid x}
    params = obj_uuids.join(" ")
    self.run_python_file(
    "/vsan-vsi.py",
    "get_dom_objects_info #{params}"
    )
  end

  def vsan_slab_stats
    self.run_python_file(
    "/vsan-vsi.py",
    "get_vsan_fastslab_stats"
    )
  end

  def run_python_file script, params = '', opts = {}
    local = "#{File.dirname(__FILE__)}/#{script}"
    self.scp.upload!(local, "/vsan-vsi.py")
    cmd = "python /vsan-vsi.py #{params} 2>/dev/null"
    jsontxt = self.exec!(cmd)
    begin
      if opts[:gzip]
        gzip = Base64.decode64(jsontxt)
        gz = Zlib::GzipReader.new(StringIO.new(gzip))
        jsontxt = gz.read
      end
      out = JSON.load(jsontxt)
    rescue
      puts "Parsing JSON failed. Cmd = #{cmd}"
      puts "Raw JSON:"
      puts jsontxt
      raise
    end
    out
  end

  def objects_on_disks disk_uuid_list
    params = disk_uuid_list.join(" ")
    self.run_python_file(
    "/vsan-vsi.py",
    "get_objects_on_disks #{params}"
    )
  end

  def daemon_status daemons
    out = {}
    daemons.each do |daemon|
      status = self.exec!("/etc/init.d/#{daemon} status")
      if status =~ /is not running/
        status = false
      else
        status = true
      end
      out[daemon] = status
    end
    out
  end

  def vsan_daemon_status
    daemon_status(["clomd", "osfsd", "swapobjd", "cmmdsd", 'vsanvpd'])
  end
end

opts :resync_stats do
  summary "Tries to determine how much needs to be resynced right now"
  arg :cluster_or_host, "Cluster or host on which to fetch the object info", :lookup => VIM::ClusterComputeResource
  opt :password, "ESX Password", :type => :string
end

def resync_stats cluster_or_host, opts
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  if cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    hosts = cluster.host
  else
    hosts = [cluster_or_host]
  end

  bytes_to_sync_per_host = {}
  hosts_props = nil

  puts "NOTE: Currently only covers reconfig induced resyncs"
  puts "NOTE: Once resync for a given object has started, no progress other than end of resync is provided"

  _run_with_rev(conn, "dev") do
    host_vsan_uuids, hosts_props, vsan_disk_uuids = _vsan_cluster_disks_info(cluster)

    connected_hosts = hosts_props.select do |k,v|
      v['runtime.connectionState'] == 'connected'
    end.keys
    hosts = connected_hosts

    hosts.first.ssh do |ssh|
      dom_objects = ssh.cmmds_find "-t DOM_OBJECT"

      dom_objects.map do |dom_obj|
        dom_components = _components_in_dom_config(dom_obj['content'])
        bytes_to_sync = dom_components.map do |dom_comp|
          dom_comp['attributes']['bytesToSync'].to_i
        end.compact.sum

        owner_host = host_vsan_uuids[dom_obj['owner']]
        bytes_to_sync_per_host[owner_host] ||= 0
        bytes_to_sync_per_host[owner_host] += bytes_to_sync
      end

    end
  end

  t = Terminal::Table.new()
  t << ['Host', 'Data to sync by owners']
  t.add_separator
  bytes_to_sync_per_host.each do |host, bytes_to_sync|
    host_name = hosts_props[host]['name']
    t << (
    [
      host_name,
      "%.2f GB" % [bytes_to_sync.to_f / 1024**3]
    ]
    )
  end

  puts t
end

opts :cluster_optimize_clom do
  summary "Optimizes CLOM memory usage"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource
  opt :password, "ESX Password", :type => :string
end

def cluster_optimize_clom cluster, opts
  conn = cluster._connection
  pc = conn.propertyCollector
  objs = nil
  _run_with_rev(conn, "dev") do
    hosts = cluster.host
    hosts_props = pc.collectMultiple(hosts, 'name')
    hosts.each do |host|
      host.ssh do |ssh|
        props = hosts_props[host]
        puts "Restarting clomd on #{props['name']} ..."
        # ssh.exec! "cp /etc/init.d/clomd /etc/init.d/clomd-old"
        # cmd = "cat /etc/init.d/clomd-old | sed 's:CLOMD_PARAM=\"${CLOMD_PARAM} -f\":CLOMD_PARAM=\"${CLOMD_PARAM} -f -r 7200\":' > /etc/init.d/clomd2"
        # ssh.exec! cmd
        # ssh.exec! "cat /etc/init.d/clomd2 | grep CLOMD_PARAM"
        # ssh.exec! "chmod +x /etc/init.d/clomd2"
        ssh.exec! "/etc/init.d/clomd stop"
        ssh.exec! "/etc/init.d/clomd start"
      end
    end
  end
  puts "Waiting 10 seconds for all clomds to settle ..."
  sleep 10
  puts "Done"
end

opts :find_orphans do
  summary "CMMDS Find"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :password, "ESX Password", :type => :string
  opt :delete_leaked_dom, "", :type => :boolean
  opt :delete_leaked_dom_openstack, "", :type => :boolean
  opt :delete_leaked_vmdks_and_vswp, "", :type => :boolean
  opt :delete_leaked_dirs, "", :type => :boolean
  opt :delete_leaked_dirs_deep, "", :type => :boolean
  opt :force_delete, "Force deletion even if DOM doesn't have quorum", :type => :boolean
end

def find_orphans cluster_or_host, opts
  conn = cluster_or_host._connection
  pc = conn.propertyCollector
  host = cluster_or_host
  if cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    hosts = cluster.host
    hosts_props = pc.collectMultiple(
    hosts,
    'runtime.connectionState',
    'configManager.vsanInternalSystem'
    )
    connected_hosts = hosts_props.select do |k,v|
      v['runtime.connectionState'] == 'connected'
    end.keys
    host = connected_hosts.first
    if !host
      err "No connected host found"
    end
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
  else
    vsanIntSys = host.configManager.vsanInternalSystem
  end

  entries = nil

  ds_list = host.datastore
  ds_props = pc.collectMultiple(ds_list, 'name', 'summary.type')
  ds = ds_props.select{|k, x| x['summary.type'] == "vsan"}.keys.first
  ds_name = ds_props[ds]['name']

  host.ssh do |ssh|
    puts "#{Time.now}: Step 1: Check for leaked DOM objects that have descriptor files (e.g. VMDKs, .vswp, .vmem, directories)"
    layoutExList = pc.collectMultiple(ds.vm, 'layoutEx').values.map{|x| x['layoutEx']}
    files = layoutExList.compact.map{|x| x.file.map{|x| x.name}}.flatten
    dirs = files.map{|x| if x =~ /^\[([^\]])+\] ([^\/]*)\//; $2; end;}.compact.uniq

    objects, leaks = ssh.vsan_find_orphan_objects(ds_name, dirs)

    puts "#{Time.now}: Found orphans:"
    leaks['vmdk'].each do |file, uuid|
      puts "VMDK #{file} (#{uuid}) not referenced in VC"
    end
    leaks['vswp'].each do |file, uuid|
      puts "Swap #{file} (#{uuid}) not referenced in VC"
    end
    leaks['vmem'].each do |file, uuid|
      puts "Swap #{file} (#{uuid}) not referenced in VC"
    end
    leaks['dirs'].each do |file, uuid|
      puts "Directory #{file} (#{uuid}) not referenced in VC"
    end
    if opts[:delete_leaked_vmdks_and_vswp]
      leaks['vmdk'].each do |file, object_uuid|
        puts "#{Time.now}: Deleting object #{object_uuid} in #{file} ..."
        cmd = "vmkfstools -U #{file}"
        puts "Running #{cmd.inspect}"
        puts ssh.exec! cmd
      end
      (leaks['vswp'] + leaks['vmem']).each do |file, object_uuid|
        puts "#{Time.now}: Deleting object #{object_uuid} in #{file} ..."
        cmd = "/usr/lib/vmware/osfs/bin/objtool delete -u #{object_uuid}"
        if opts[:force_delete]
          cmd += " -f"
        end
        puts "Running #{cmd.inspect}"
        puts ssh.exec! cmd
        cmd = "rm -f #{file}"
        puts "Running #{cmd.inspect}"
        puts ssh.exec! cmd
      end
    end
    if opts[:delete_leaked_dirs] || opts[:delete_leaked_dirs_deep]
      leaks['dirs'].each do |ufn, object_uuid|
        puts "#{Time.now}: Deleting directory #{object_uuid}/#{ufn} ..."
        if opts[:delete_leaked_dirs_deep]
          cmd = "rm -rf /vmfs/volumes/#{ds_name}/#{object_uuid}/.dvsData"
          puts "Running #{cmd.inspect}"
          puts ssh.exec! cmd
          cmd = "rm -rf /vmfs/volumes/#{ds_name}/#{object_uuid}/*"
          puts "Running #{cmd.inspect}"
          puts ssh.exec! cmd
          cmd = "rm -rf /vmfs/volumes/#{ds_name}/#{object_uuid}/.*.lck"
          puts "Running #{cmd.inspect}"
          puts ssh.exec! cmd
          cmd = "ls -la /vmfs/volumes/#{ds_name}/#{object_uuid}/"
          puts "Running #{cmd.inspect}"
          puts ssh.exec! cmd
        end

        cmd = "/usr/lib/vmware/osfs/bin/osfs-rmdir /vmfs/volumes/#{ds_name}/#{object_uuid}"
        puts "Running #{cmd.inspect}"
        puts ssh.exec! cmd
      end
    end

    puts "#{Time.now}: Step 2: Check for leaked DOM objects that can't be attributed to anything in the system"
    dom_objects = ssh.cmmds_find "-t DOM_OBJECT"
    dom_objects = Hash[dom_objects.map{|x| [x['uuid'], x]}]

    objects.map{|k,v| v.values}.flatten.each do |uuid|
      dom_objects.delete(uuid)
    end

    if !dom_objects.empty?
      begin
        extattrs = vsanIntSys.query_vsan_obj_extattrs(
        :uuids => dom_objects.keys
        )
      rescue Exception => ex
        puts "Warning: Failed to get extended attributes: #{ex.class}: #{ex.message}"
        pp ex
        puts "Warning: Extended attributes won't be available"
      end
      if extattrs

      end
    end

    puts "#{Time.now}: Found #{dom_objects.length} suspected DOM object leaks"
    dom_objects.each do |uuid, dom_object|
      puts "DOM object #{uuid} is a suspected leak"
      doDelete = opts[:delete_leaked_dom]
      if extattrs && extattrs[uuid]
        extattr = extattrs[uuid]
        puts "  class: %s, path: %s, exists: %s" % [
          extattr['Object class'],
          extattr['Object path'],
          (extattr['pathexists'] == nil) ? 'unknown' : extattr['pathexists'],
        ]
        doDelete ||= (opts[:delete_leaked_dom_openstack] &&
        extattr['pathexists'] == false &&
        ["vdisk", "vmswap"].member?(extattr['Object class']) &&
        extattr['Object path'] != nil &&
        extattr['Object path'] != "(null)")
        #        puts "Do delete: #{doDelete}"
      end

      if doDelete
        puts "Attempting to delete suspected leak"
        cmd = "/usr/lib/vmware/osfs/bin/objtool delete -u #{uuid}"
        if opts[:force_delete]
          cmd += " -f"
        end
        puts "Running #{cmd.inspect}"
        puts ssh.exec! cmd
      end
    end

    puts "#{Time.now}: Step 3: Check for leaked LSOM components that are not part of any DOM object"
    # XXX

  end

end

opts :congestion_stats do
  summary "Congestion stats"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :password, "ESX Password", :type => :string
end

def congestion_stats cluster_or_host, opts = {}
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  if cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    hosts = cluster.host
  else
    hosts = [cluster_or_host]
  end

  hosts_props = pc.collectMultiple(hosts, 'name', 'runtime.connectionState')
  connected_hosts = hosts_props.select do |k,v|
    v['runtime.connectionState'] == 'connected'
  end.keys
  hosts = connected_hosts

  hosts_lsomcongestion = {}
  hosts_domdelays = {}
  _run_with_rev(conn, "dev") do
    hosts.map do |host|
      Thread.new do
        host.ssh do |ssh|
          hosts_lsomcongestion[host] = ssh.lsom_congestion_from_traces
          hosts_domdelays[host] = ssh.dom_delays_from_traces
        end
      end
    end.each{|t| t.join}
  end

  puts "DOM: Delays injected"
  t = Terminal::Table.new()
  t << ['Host', 'Object', 'DOM average delay']
  t.add_separator
  hosts.each_with_index do |host, i|
    host_props = hosts_props[host]
    dom_delays = hosts_domdelays[host]

    dom_delays.sort_by{|x| x['average delay']}.each do |dom_delay|
      t << [
        host_props['name'],
        dom_delay['objUUID'],
        dom_delay['average delay'],
      ]
    end

    if i != hosts.length - 1
      t.add_separator
    end
  end
  puts t
  puts

  puts "LSOM: Reported congestion"
  t = Terminal::Table.new()
  t << ['Host', 'IOPS cong.', 'Bucketlist cong.', 'Memory cong.', 'MM cong.', 'SSD cong.']
  t.add_separator
  hosts.each_with_index do |host, i|
    host_props = hosts_props[host]
    lsom_congestion = hosts_lsomcongestion[host]

    if lsom_congestion.length > 0
      x = Hash[lsom_congestion.first.keys.map do |key|
        values = lsom_congestion.map{|x| x[key].to_f}
        [key, (values.sum / values.length).to_i]
      end]
      t << [
        host_props['name'],
        x['iopsCongestion'],
        x['blCongestion'],
        x['memCongestion'],
        x['mmCongestion'],
        x['ssdCongestion'],
      ]
    end
    if lsom_congestion.length == 0
      t << [host_props['name'], 0, 0, 0, 0, 0]
    end

    if i != hosts.length - 1
      t.add_separator
    end
  end
  puts t
end

opts :memory_stats do
  summary "CMMDS Find"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :password, "ESX Password", :type => :string
end

def memory_stats cluster_or_host, opts = {}
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  if cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    hosts = cluster.host
  else
    hosts = [cluster_or_host]
  end

  hosts_props = pc.collectMultiple(hosts, 'name', 'runtime.connectionState')
  connected_hosts = hosts_props.select do |k,v|
    v['runtime.connectionState'] == 'connected'
  end.keys
  hosts = connected_hosts

  hosts_memstats = {}
  hosts_heapstats = {}
  hosts_slabstats = {}
  _run_with_rev(conn, "dev") do
    hosts.map do |host|
      Thread.new do
        host.ssh do |ssh|
          hosts_memstats[host] = ssh.vsan_mem_group_stats
          hosts_heapstats[host] = ssh.vsan_mem_heap_stats
          hosts_slabstats[host] = ssh.vsan_slab_stats
        end
      end
    end.each{|t| t.join}
  end

  hosts.each do |host|
    host_props = hosts_props[host]
    mem_stats = hosts_memstats[host]
    heap_stats = hosts_heapstats[host]
    slabs_stats = hosts_slabstats[host]
    puts "VSAN Memory stats for host #{host_props['name']}"

    t = Terminal::Table.new()
    t << ['Group', 'eMin', 'eMinPeak', 'rMinPeak', "Max"]
    t.add_separator
    mem_stats.each_with_index do |group_stats, i|
      t << [
        group_stats['name'],
        "%.2f MB (%.2f %%)" % [
        group_stats['eMin'].to_f / 1024**1,
        group_stats['eMin'].to_f * 100 / group_stats['max'].to_f,
        ],
        "%.2f MB" % [group_stats['eMinPeak'].to_f / 1024**1],
        "%.2f MB" % [group_stats['rMinPeak'].to_f / 1024**1],
        "%.2f MB" % [group_stats['max'].to_f / 1024**1],
      ]
    end
    puts t

    t = Terminal::Table.new()
    t << ['Heap', 'Used', 'Avail', 'Size', 'MaxUsed', "Max"]
    t.add_separator
    heap_stats.each_with_index do |group_stats, i|
      #pp group_stats
      t << [
        group_stats['name'],
        "%.2f MB (%.2f %%)" % [
        group_stats['used'].to_f / 1024**2,
        group_stats['used'].to_f * 100 / group_stats['max'].to_f,
        ],
        "%.2f MB" % [group_stats['avail'].to_f / 1024**2],
        "%.2f MB" % [group_stats['size'].to_f / 1024**2],
        "%d %%" % [100 - group_stats['lowPctFreeOfMax'].to_f],
        "%.2f MB" % [group_stats['max'].to_f / 1024**2],
      ]
    end
    puts t

    t = Terminal::Table.new()
    t << ['FastSlab', 'Used objects', "Max objects"]
    t.add_separator
    slabs_stats.sort_by do |name, slab|
      slab['curObjs'].to_f * 100 / slab['maxObj'].to_f
    end.each do |name, slab|
      t << [
        name,
        "%d (%.2f %%)" % [
        slab['curObjs'],
        slab['curObjs'].to_f * 100 / slab['maxObj'].to_f,
        ],
        slab['maxObj'],
      ]
    end
    puts t
    puts
  end
end

opts :lsom_log_stats do
  summary "Show LSOM log stats"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :password, "ESX Password", :type => :string
end

def lsom_log_stats cluster_or_host, opts = {}
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  if cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    hosts = cluster.host
  else
    hosts = [cluster_or_host]
  end

  hosts_props = pc.collectMultiple(hosts, 'name', 'runtime.connectionState')
  connected_hosts = hosts_props.select do |k,v|
    v['runtime.connectionState'] == 'connected'
  end.keys
  hosts = connected_hosts

  hosts_lsomdisks = {}
  hosts_plogdisks = {}
  _run_with_rev(conn, "dev") do
    hosts.map do |host|
      Thread.new do
        host.ssh do |ssh|
          hosts_lsomdisks[host] = ssh.run_python_file("/vsan-vsi.py", "get_lsomdisks")
          hosts_plogdisks[host] = ssh.run_python_file("/vsan-vsi.py", "get_plogdisks")
        end
      end
    end.each{|t| t.join}
  end

  t = Terminal::Table.new()
  t << ['Host', 'SSD UUID', 'llog log/data', 'plog log/data', 'free wb', 'accounted plog']

  hosts.each do |host|
    host_props = hosts_props[host]
    lsomdisks = hosts_lsomdisks[host]
    plogdisks = hosts_plogdisks[host]

    t.add_separator
    lsomdisks.select{|k, x| x['type'] == 'cache'}.each do |k, disk|
      ploginfo = plogdisks[k]
      total_plog = ploginfo['mddata'].values.map{|x| x['total']}.max
      sum_md_plog = ploginfo['mddata'].values.map{|x| x['md']}.sum
      t << [
        host_props['name'],
        disk['uuid'],
        "%.2f/%.2f GB" % [
        (disk['llogLogSpace'].to_f / 1024**3),
        (disk['llogDataSpace'].to_f / 1024**3),
        ],
        "%.2f/%.2f GB" % [
        (disk['plogLogSpace'].to_f / 1024**3),
        (disk['plogDataSpace'].to_f / 1024**3),
        ],
        "%.2f %%" % (disk['wbFreeSpace'].to_f * 100 / disk['wbSize']),
        "%.2f %%" % (sum_md_plog.to_f * 100 / total_plog),
      ]
    end

  end
  puts t
end

opts :diagnostics do
  summary "Diagnostics"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :password, "ESX Password", :type => :string
  opt :auto_correct, "Take corrective actions", :type => :boolean
  opt :skip_vm_create, "Skip the VM create test", :type => :boolean
end

def diagnostics cluster_or_host, opts = {}
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  if cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    hosts = cluster.host
  else
    hosts = [cluster_or_host]
  end

  hosts_props = pc.collectMultiple(hosts, 'name', 'runtime.connectionState')
  connected_hosts = hosts_props.select do |k,v|
    v['runtime.connectionState'] == 'connected'
  end.keys
  hosts = connected_hosts

  hosts_memstats = {}
  hosts_heapstats = {}
  hosts_lsomdisks = {}
  hosts_daemonstatus = {}
  _run_with_rev(conn, "dev") do
    hosts.map do |host|
      Thread.new do
        host.ssh do |ssh|
          hosts_memstats[host] = ssh.vsan_mem_group_stats
          hosts_heapstats[host] = ssh.vsan_mem_heap_stats
          hosts_lsomdisks[host] = ssh.run_python_file("/vsan-vsi.py", "get_lsomdisks")
          hosts_daemonstatus[host] = ssh.vsan_daemon_status
        end
      end
    end.each{|t| t.join}
  end

  need_sleep = false
  hosts.each do |host|
    host_props = hosts_props[host]
    mem_stats = hosts_memstats[host]
    heap_stats = hosts_heapstats[host]
    lsomdisks = hosts_lsomdisks[host]
    daemonstatus = hosts_daemonstatus[host]

    puts "Running diagnostics on host #{host_props['name']} ..."
    mem_stats.select do |x|
      max = x['max'].to_i
      if max == 0
        puts "Daemon #{x['name'].inspect} doesn't report a max?!"
        false
      else
        x['eMin'].to_i * 100 / max >= 98
      end
    end.each do |x|
      puts "Daemon #{x['name'].inspect} is above 98% of its memory limit"
      if opts[:auto_correct]
        puts "Restarting #{x['name'].inspect} ..."
        host.ssh do |ssh|
          ssh.exec! "/etc/init.d/#{x['name']} stop"
          ssh.exec! "/etc/init.d/#{x['name']} start"
        end
        need_sleep = true
      end
    end
    lsomdisks.select{|k,v| v['type'] == 'cache'}.each do |k,v|
      free_wb_pct = (v['wbFreeSpace'].to_f * 100 / v['wbSize'])
      if free_wb_pct < 5.0
        disks_info = _vsan_host_disks_info host, host_props['name']
        disk_info = disks_info[k]
        disk_name = disk_info ? disk_info.DisplayName : k
        puts "Free write buffer of SSD #{disk_name}: %.2f%%" % free_wb_pct
      end
    end
    daemonstatus.each do |daemon, running|
      if !running
        puts "Daemon #{daemon.inspect} is not running"
      end
    end

    puts
  end

  if need_sleep
    puts "Restarted agents, sleeping for 15 seconds to let them finish starting"
    sleep 15
    puts "Done"
    puts
  end

  if !opts[:skip_vm_create] && cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    datastores = cluster.datastore
    ds_props = pc.collectMultiple(datastores, 'name', 'summary.type')
    ds = ds_props.select{|ds, x| x['summary.type'].downcase == 'vsan'}.keys.first
    ds_name = ds_props[ds]['name']
    dc = cluster.parent
    if !dc.is_a?(VIM::Datacenter)
      dc = dc.parent
    end
    vm_folder = dc.vmFolder

    puts "Creating one VM per host ... (timeout = 300 sec)"
    result = shell.cmds[:diagnostics].slate._vm_create(
    [cluster], ds, vm_folder,
    :timeout => 300
    )

    errors = result.select{|h, x| x['status'] != 'green'}
    errors.each do |host, info|
      puts "Failed to create VM on host #{host} (in cluster #{info['cluster']}): #{info['error']}"
      if info['error_detail']
        info['error_detail'].each do |msg|
          puts "  #{msg.key}: #{msg.message}"
        end
      end
    end
    if errors.length == 0
      puts "All hosts successfully created VMs on datastore #{ds_name.inspect}"
    end
  end
end

opts :fix_liveness do
  summary "Attempts to fix liveness of VMs and DOM objects"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :password, "ESX Password", :type => :string
  opt :nofix, "Don't fix", :type => :boolean
end

def fix_liveness cluster_or_host, opts
  err "Deprecated. Use 'vsan.check_state --refresh-state' instead"
end

def _move_owner entry, disks, hostUuidMap, desthost, vsanIntSys, hosts_props
  objuuid = entry['uuid']
  comps = _components_in_dom_config(entry['content'])
  comps = comps.map{|x| x['host'] = disks[x['diskUuid']]; x}
  ownerhost = hostUuidMap[entry['owner']]
  desthostUuid = hostUuidMap.invert[desthost]
  puts "  Object #{objuuid} resides on %s, moving to %s" % [
    hosts_props[ownerhost]['name'], hosts_props[desthost]['name']
  ]

  winner = comps.find do |x|
    x['host'] == desthost && x['attributes']['componentState'] == 5
  end
  if !winner
    raise "Didn't find any ACTIVE component on destination host"
  end
  winner = winner['componentUuid']
  puts "  Picked component to win the election: #{winner}"

  comps.map{|x| x['host']}.uniq.map do |host|
    Thread.new do
      host.ssh do |ssh|
        cmd = "vsish -e set /vmkModules/vsan/dom/forceOwnerUUID #{winner}"
        puts "  Running on #{hosts_props[host]['name']}: #{cmd}"
        out = ssh.exec!(cmd)
        if out && out.strip.length > 0
          puts(out)
        end
      end
    end
  end.each{|t| t.join}
  ownerhost.ssh do |ssh|
    cmd = "vsish -e set /vmkModules/vsan/dom/ownerAbdicate #{objuuid}"
    puts "  Running on #{hosts_props[ownerhost]['name']}: #{cmd}"
    out = ssh.exec!(cmd)
    if out && out.strip.length > 0
      puts(out)
    end
  end
  done = false
  t1 = Time.now
  while !done && (Time.now - t1) < 30.0
    sleep(1)
    entries = vsanIntSys.query_cmmds([
      {:type => 'DOM_OBJECT', :uuid => objuuid}
    ])
    if entries.length != 1 || entries[0]['owner'] != desthostUuid
      next
    end
    done = true
  end
  if !done
    puts "  Timeout: Owner didn't change to target host"
  end
  comps.map{|x| x['host']}.uniq.map do |host|
    Thread.new do
      host.ssh do |ssh|
        cmd = "vsish -e set /vmkModules/vsan/dom/forceOwnerUUID 00000000-0000-0000-0000-000000000000"
        puts "  Running on #{hosts_props[host]['name']}: #{cmd}"
        out = ssh.exec!(cmd)
        if out && out.strip.length > 0
          puts(out)
        end
      end
    end
  end.each{|t| t.join}
end

opts :distribute_owners do
  summary "Mess with owner distribution"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :password, "ESX Password", :type => :string
  opt :obj, "Object to move", :type => :string
  opt :desthost, "Destination host", :type => :string
end

def distribute_owners cluster_or_host, opts
  conn = cluster_or_host._connection
  pc = conn.propertyCollector
  if cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    hosts = cluster.host
  else
    hosts = [host]
  end

  _run_with_rev(conn, "dev") do
    hosts_props = pc.collectMultiple(hosts,
    'name',
    'runtime.connectionState',
    'configManager.vsanSystem',
    'configManager.vsanInternalSystem'
    )
    connected_hosts = hosts_props.select do |k,v|
      v['runtime.connectionState'] == 'connected'
    end.keys
    host = connected_hosts.first
    if !host
      err "Couldn't find any connected hosts"
    end
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']

    vsanSysList = Hash[hosts_props.map do |host, props|
      [host, props['configManager.vsanSystem']]
    end]
    clusterInfos = pc.collectMultiple(vsanSysList.values,
    'config.clusterInfo')
    hostUuidMap = Hash[vsanSysList.map do |host, sys|
      [clusterInfos[sys]['config.clusterInfo'].nodeUuid, host]
    end]

    hostnameToHost = Hash[hosts_props.map do |k,v|
      [v['name'], k]
    end]
    if opts[:desthost]
      desthost = hostnameToHost[opts[:desthost]]
      if !desthost
        err "Couldn't find dest host"
      end
    end

    objects = vsanIntSys.query_cmmds([{:type => 'DOM_OBJECT'}])

    disks = vsanIntSys.query_cmmds([{:type => 'DISK'}])

    disks = Hash[disks.map do |disk|
      [disk['uuid'], hostUuidMap[disk['owner']]]
    end]

    clientHostMap = {}

    hostClientMap = Hash[connected_hosts.map do |host|
      clients = []
      host.ssh do |ssh|
        res = ssh.run_python_file("/vsan-vsi.py", "get_dom_clients")
        clients = res['clients']
      end

      clients.each do |client|
        clientHostMap[client] ||= []
        clientHostMap[client] << host
      end

      [host, clients]
    end]

    objuuid = opts[:obj]
    objects.each do |entry|
      if objuuid && entry['uuid'] != objuuid
        next
      end

      curhost = hostUuidMap[entry['owner']]
      if !opts[:desthost]
        clients = clientHostMap[entry['uuid']]
        if clients && clients.length == 1
          desthost = clients.first
          if desthost == curhost
            puts "#{entry['uuid']}: Owner already colocated with client, do nothing"
            next
          else
            puts "#{entry['uuid']}: Colocating owner with client"
          end
        elsif clients && clients.length > 1
          puts "#{entry['uuid']}: Multiple clients, do nothing"
          next
        else
          puts "#{entry['uuid']}: No clients, do nothing"
          next
        end
      end

      begin
        _move_owner(entry, disks, hostUuidMap, desthost, vsanIntSys, hosts_props)
      rescue Exception => ex
        puts "#{ex.class}: #{ex.message}"
      end
    end
  end
end

opts :perform_maintenance do
  summary "Enter MM, optinally reboot, Exit MM"
  arg :host, nil, :lookup => VIM::HostSystem, :multi => true
  opt :vsan_mode, "Actions to take for VSAN backed storage", :type => :string, :default => "ensureObjectAccessibility"
  opt :reboot, "Whether to perform a reboot while in MM", :type => :boolean
  opt :iterations, "How many iterations to perform", :type => :int, :default => 1
end

def perform_maintenance hosts, opts
  def run_commands cmds
    cmds.each do |cmd|
      if cmd =~ /^\/(.*)/
        cmd = $1
        puts "#{Time.now}: Running Ruby cmd: #{cmd}"
        shell.eval_ruby(cmd)
      else
        puts "#{Time.now}: Running RVC cmd: #{cmd}"
        shell.eval_command(cmd)
      end
    end
  end

  (1..opts[:iterations]).each do |i|
    if opts[:iterations] > 1
      puts "#{Time.now}: Starting iteration #{i}"
      puts "#{Time.now}: ======================="
    end
    hosts.each do |host|
      cluster = host.parent
      if !cluster.is_a?(VIM::ClusterComputeResource)
        err "Couldn't identify the VSAN cluster"
      end
      clusterConf = cluster.configurationEx
      if !clusterConf.drsConfig || !clusterConf.drsConfig.enabled
        err "DRS is not enabled on VSAN cluster, no automatic migrations"
      end
      shell.fs.marks['h'] = [host]
      shell.fs.marks['maintenance_cluster'] = [cluster]
      puts "#{Time.now}: Performing maintenance on host #{host.name}"
      cmds = [
        # Consider VSAN mode
        "vsan.enter_maintenance_mode --evacuate-powered-off-vms ~h --no-wait --vsan-mode #{opts[:vsan_mode]}",
        "/sleep 30",
        "cluster.recommendations ~maintenance_cluster",
        "cluster.apply_recommendations ~maintenance_cluster",
        "cluster.apply_recommendations ~maintenance_cluster",
        "cluster.apply_recommendations ~maintenance_cluster",
        "/sleep 5",
        "cluster.apply_recommendations ~maintenance_cluster",
        "cluster.apply_recommendations ~maintenance_cluster",
        "cluster.apply_recommendations ~maintenance_cluster",
        "/sleep 15",
        "vsan.resync_dashboard ~maintenance_cluster",
        "/progress(_h.recentTask.select{|x| x.info.name == 'EnterMaintenanceMode_Task'})",
      ]
      run_commands cmds

      if opts[:reboot]
        cmds = [
          "host.reboot --wait ~h",
        ]
        run_commands cmds
      end

      cmds = [
        "host.exit_maintenance_mode ~h",
        "table -f name -f state.connection -f num.vms -f num.poweredonvms " +
        "-f cpuusage -f memusage -f uptime -f state.maintenancemode " +
        "-f build " +
        "~/computers/*/hosts/*",
      ]
      run_commands cmds
      puts "#{Time.now}: Done with maintenance on host #{host.name}"
      puts
    end
  end
end

opts :dom_stuck_ios do
  summary "Find IO's stuck in DOM"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :age, "Age in seconds", :type => :int, :default => 30
  opt :password, "ESX Password", :type => :string
end

def dom_stuck_ios cluster_or_host, opts = {}
  conn = cluster_or_host._connection
  pc = conn.propertyCollector
  _run_with_rev(conn, "dev") do
    if opts[:age] < 30
      err "Can't dump IOs younger than 30 seconds"
    end
    if cluster_or_host.is_a?(VIM::ClusterComputeResource)
      cluster = cluster_or_host
      hosts = cluster.host
    else
      hosts = [cluster_or_host]
    end
    all_hosts = pc.collectMultiple(hosts, 'name')
    host = all_hosts.first
    if !host
      err "Couldn't find any hosts"
    end
    iomap = {}
    hosts.each do |host|
      begin
        host.ssh do |ssh|
          (1..3).each do |i|
            cmd = "vsish -e set /vmkModules/vsan/dom/dumpStuckIO #{i} #{opts[:age]}"
            ssh.exec! cmd
          end
        end
      rescue Exception => ex
        pp [host.name, ex.class, ex.message]
      end
    end
    sleep 5
    hosts.each do |host|
      begin
        host.ssh do |ssh|
          cmd = "tail -100 /var/log/vmkernel.log | " +
          "awk '/DOMDumpStuckIoOpDispatch/{print $4,$6,$8,$10,$12,$14}'"
          out = ssh.exec! cmd
          if out && out.strip.length > 0
            lines = out.split(/\n/)
            lines.each do |line|
              i = line.split
              i[3].chop!
              arr = [i[0].chop,i[1],i[2].chop,i[4].chop,i[5],host.name]
              if iomap.has_key? i[3]
                iomap[i[3]] << arr
              else
                iomap[i[3]] = [arr]
              end
            end
          end
        end
      rescue Exception => ex
        pp [host.name, ex.class, ex.message]
      end
    end
    if !iomap.empty?
      iomap.each do |k,v|
        puts "Op ID: #{k}:"
        v.each do |io|
          if io[3] == "1"
            domtype = "DOM client"
          elsif io[3] == "2"
            domtype = "DOM owner"
          elsif io[3] == "3"
            domtype = "DOM component"
          end
          puts "  Op: #{io[1]} Type: #{io[2]} UUID: #{io[0]}" +
          " stuck in #{domtype} on #{io[5]} for #{io[4]} ms."
        end
      end
    else
      puts "Can't find IO's stuck for more than #{opts[:age]} seconds."
    end
  end
end

opts :device_add_disk do
  summary "Add a hard drive to a virtual machine"
  arg :vm, nil, :lookup => VIM::VirtualMachine
  arg :path, "Filename on the datastore", :lookup_parent => VIM::Datastore::FakeDatastoreFolder, :required => false
  opt :path_string, "Filename on the datastore in string", :type => :string, :default => ""
  opt :size, 'Size', :default => '10Gi'
  opt :controller, 'Virtual controller', :type => :string, :lookup => VIM::VirtualController
  opt :file_op, 'File operation (create|reuse|replace)', :default => 'create'
  opt :no_thin, 'Use thick provisioning', :type => :boolean
  opt :profile_id, "Storage Policy id", :type => :string
  opt :multi_writer, ":sharingNone or :sharingMultiWriter", :type => :boolean, :default => false
end

def device_add_disk vm, path, opts
  controller, unit_number = pick_controller vm, opts[:controller], [VIM::VirtualSCSIController, VIM::VirtualIDEController]
  if unit_number == 7
    unit_number += 1
  end
  id = "disk-#{controller.key}-#{unit_number}"

  if path
    dir, file = *path
    filename = "#{dir.datastore_path}/#{file}"
  elsif opts[:path_string] == ""
    filename = "#{File.dirname(vm.summary.config.vmPathName)}/#{id}.vmdk"
  else
    filename = opts[:path_string]
  end

  opts[:file_op] = nil if opts[:file_op] == 'reuse'
  profile = nil
  profileId = ""

  if opts[:profile_id]
    profileId = opts[:profile_id]
  end

  if profileId != ""
    profile = [VIM::VirtualMachineDefinedProfileSpec(
        :profileId => profileId,
              )]
  end

  sharing = :sharingNone
  diskmode = :persistent  
  eager = false
  if opts[:multi_writer]
    sharing = :sharingMultiWriter
    diskmode = :independent_persistent
    eager = true
  end
  
  spec = {
    :deviceChange => [
    {
    :operation => :add,
    :fileOperation => opts[:file_op],
    :device => VIM::VirtualDisk(
    :key => -1,
    :backing => VIM.VirtualDiskFlatVer2BackingInfo(
    :fileName => filename,
    :sharing => sharing,
    :diskMode => diskmode,
    :eagerlyScrub => eager,
    :thinProvisioned => !(opts[:no_thin] == true)
    ),
    :capacityInKB => MetricNumber.parse(opts[:size]).to_i/1024,
    :controllerKey => controller.key,
    :unitNumber => unit_number
    ),
    :profile => profile,
    },
    ]
  }

  conn = vm._connection
  _run_with_rev(conn, "dev") do
    task = vm.ReconfigVM_Task(:spec => spec)
    result = progress([task])[task]
    if result == nil
      new_device = vm.collect('config.hardware.device')[0].grep(VIM::VirtualDisk).last
      puts "Added device #{new_device.name}"
      if opts[:file_op] == 'create' and opts[:multi_writer] and $path_params
	if $path_params.has_key? vm.name
          $path_params[vm.name] << "#{new_device.backing.fileName}"
	else
	  $path_params[vm.name] = ["#{new_device.backing.fileName}"]
	end
      end
    
    else
      err result.localizedMessage
    end
  end
end

def pick_controller vm, controller, controller_classes
  existing_devices, = vm.collect 'config.hardware.device'

  controller ||= existing_devices.find do |dev|
    controller_classes.any? { |klass| dev.is_a? klass } &&
    dev.device.length < 2
  end
  err "no suitable controller found" unless controller

  used_unit_numbers = existing_devices.select { |dev| dev.controllerKey == controller.key }.map(&:unitNumber)
  unit_number = 0
  if used_unit_numbers.max == 15 and used_unit_numbers.size < 15
    sample = [0,1,2,3,4,5,6,8,9,10,11,12,13,14,15]
    unit_number = (sample-used_unit_numbers)[0]
  else    
    unit_number = (used_unit_numbers.max||-1) + 1
  end
  [controller, unit_number]
end

opts :create_vmfs_datastore do
  summary "Create a VMFS datastore"
  arg :host, nil, :lookup => VIM::HostSystem
  arg :devicePath, nil, :type => :string
  arg :name, nil, :type => :string
end

def create_vmfs_datastore host, devicePath, name
  dss = host.configManager.datastoreSystem
  disks = dss.QueryAvailableDisksForVmfs
  disk = disks.find{|x| x.devicePath == devicePath}
  if !disk
    puts "#{devicePath} not an option. Available disks:"
    disks.each{|x| puts "#{x.devicePath}  -- #{x.displayName} #{x.vendor} #{x.model}"}
    err "Please select a valid disk"
  end
  datastores = []
  specs = dss.QueryVmfsDatastoreCreateOptions(:devicePath => disk.devicePath)
  specs.each do |spec|
    spec.spec.vmfs.volumeName = name
    ds = dss.CreateVmfsDatastore(:spec => spec.spec)
    datastores << ds
  end
  datastores
end

opts :config_syslog do
  summary "Configure Syslog"
  arg :entity, nil, :lookup => [VIM, VIM::HostSystem, VIM::ComputeResource, VIM::ClusterComputeResource]
  arg :ip, nil, :type => :string
  opt :vc_root_pwd, "VC root password for SSH access", :default => "vmware"
end

def config_syslog entity, ip, opts
  if entity.is_a?(VIM)
    puts "#{Time.now}: Finding all Hosts inside VC"
    $shell.fs.marks['vcrvc'] = entity
    hosts = []
    hosts += $shell.fs.lookup("~vcrvc/*/computers/*/host")
    hosts += $shell.fs.lookup("~vcrvc/*/computers/*/hosts/*")
  elsif entity.is_a?(VIM::ComputeResource)
    hosts = entity.host
  else
    hosts = [entity]
  end
  if hosts.length == 0
    err "No hosts found"
  end
  conn = hosts.first._connection
  pc = conn.propertyCollector

  lock = Mutex.new
  _run_with_rev(conn, "dev") do
    hosts_props = pc.collectMultiple(hosts,
    'name',
    'runtime.connectionState'
    )
    connected_hosts = hosts_props.select do |k,v|
      v['runtime.connectionState'] == 'connected'
    end.keys
    host = connected_hosts.first
    if !connected_hosts.first
      err "Couldn't find any connected hosts"
    end

    puts "#{Time.now}: Configuring all ESX hosts ..."
    loghost = "udp://#{ip}:514"
    hosts.map do |host|
      Thread.new do
        begin
          c1 = conn.spawn_additional_connection
          host  = host.dup_on_conn(c1)
          hostName = host.name
          lock.synchronize do
            puts "#{Time.now}: Configuring syslog on #{hostName}"
          end
          syslog = host.esxcli.system.syslog
          syslog.config.set(:loghost => loghost)
          syslog.reload
        rescue Exception => ex
          puts "#{Time.now}: #{host.name}: Got exception: #{ex.class}: #{ex.message}"
        end
      end
    end.each{|t| t.join}
    puts "#{Time.now}: Done configuring syslog on all hosts"

    local = "#{File.dirname(__FILE__)}/configurevCloudSuiteSyslog.sh"
    osType = conn.serviceContent.about.osType
    if File.exists?(local) && osType == "linux-x64"
      puts "#{Time.now}: Configuring VCVA ..."
      Net::SSH.start(conn.host, "root", :password => opts[:vc_root_pwd],
      :verify_host_key => :never) do |ssh|
        ssh.scp.upload!(local, "/root/configurevCloudSuiteSyslog.sh")
        cmd = "sh /root/configurevCloudSuiteSyslog.sh vcsa #{ip}"
        puts "#{Time.now}: Running '#{cmd}' on VCVA"
        puts ssh.exec!(cmd)
      end
      puts "#{Time.now}: Done with VC"
    else
      puts "#{Time.now}: VC isn't Linux, skipping ..."
    end
  end
  puts "#{Time.now}: Done"
end

def _run_with_rev conn, rev
  old_rev = conn.rev
  begin
    conn.rev = rev
    yield
  ensure
    conn.rev = old_rev
  end
end

opts :restore_st_vms do
  summary "Restore ST VMs"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
end

def _registerVmsOnHost(host, vmfolder, vmNames, dsName,
  existingVmxPaths, existingVmNames)
  rp = host.parent.resourcePool
  tasks = []
  vmNames.select do |vmName|
    vmxPath = "[#{dsName}] #{vmName}/#{vmName}.vmx"
    !existingVmxPaths.member?(vmxPath) && !existingVmNames.member?(vmName)
  end.each do |vmName|
    vmxPath = "[#{dsName}] #{vmName}/#{vmName}.vmx"
    puts "Registering #{vmxPath} ..."
    task = vmfolder.RegisterVM_Task(
    :name => vmName,
    :path => vmxPath,
    :asTemplate => false,
    :host => host,
    :pool => rp
    )
    tasks << task
    if tasks.length > 30
      progress(tasks)
      tasks = []
    end
  end
  if tasks.length > 0
    progress(tasks)
  end
end

def restore_st_vms cluster_or_host, opts = {}
  this = $shell.fs.lookup(".").first
  if !this || !this.is_a?(VIM::Folder)
    err "Need to execute command in a VM folder"
  end
  conn = cluster_or_host._connection
  pc = conn.propertyCollector
  if cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    hosts = cluster.host
  else
    hosts = [host]
  end

  _run_with_rev(conn, "dev") do
    hosts_props = pc.collectMultiple(hosts,
    'name',
    'runtime.connectionState',
    'configManager.vsanSystem',
    'configManager.vsanInternalSystem'
    )
    connected_hosts = hosts_props.select do |k,v|
      v['runtime.connectionState'] == 'connected'
    end.keys
    host = connected_hosts.first
    if !host
      err "Couldn't find any connected hosts"
    end
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
    vsanSys = hosts_props[host]['configManager.vsanSystem']
    vsanDs = host.datastore.find{|x| x.summary.type == "vsan"}
    if !vsanDs
      err "Couldn't find VSAN datastore"
    end
    dsName = vsanDs.name
    vms = vsanDs.vm
    vms_props = pc.collectMultiple(vms, "name", "summary.config.vmPathName")

    existingVmxPaths = vms_props.values.map{|x| x["summary.config.vmPathName"]}
    existingVmNames = vms_props.values.map{|x| x["name"]}

    clusterUuid = vsanSys.config.clusterInfo.uuid
    clusterUuid = clusterUuid.gsub("-", "")
    clusterUuid = "%s-%s" % [clusterUuid[0..15], clusterUuid[16..32]]

    vmNames = nil
    host.ssh do |ssh|
      osfsLsBin = "/usr/lib/vmware/osfs/bin/osfs-ls"

      dsPath = "/vmfs/volumes/vsan:#{clusterUuid}/"
      cmd = "#{osfsLsBin} #{dsPath} | grep io | grep vmwpv"
      puts cmd
      vmNames = ssh.exec!(cmd)
      if !vmNames
        err "Expected osfs-ls to return something, but it didn't"
      end
      vmNames = vmNames.split("\n")
    end
    vmNames = vmNames.group_by{|x| x =~ /^io-([^-]*)-/; $1}

    hostWithVms = []
    hostWithoutVms = []
    connected_hosts.each do |host|
      hostname = hosts_props[host]['name']
      if vmNames[hostname]
        puts "Found VMs for #{hostname}"
        hostWithVms << host
      else
        puts "No VMs for #{hostname} found"
        hostWithoutVms << host
        next
      end
      _registerVmsOnHost(
      host, this, vmNames[hostname], dsName,
      existingVmxPaths, existingVmNames
      )
    end

    hostnames = hosts_props.map{|host, x| x['name']}
    unknownHosts = vmNames.keys.select{|hostname| !hostnames.member?(hostname)}
    pp hostWithoutVms
    pp hostWithVms
    pp unknownHosts
    while unknownHosts.length > 0 && hostWithoutVms.length > 0
      hostname = unknownHosts.pop
      host = hostWithoutVms.pop
      puts "Mapping #{hostname} to #{host.name} ..."
      _registerVmsOnHost(
      host, this, vmNames[hostname], dsName,
      existingVmxPaths, existingVmNames
      )
    end
    if unknownHosts.length > 0
      puts "WARNING: Couldn't map hosts #{unknownHosts} to any host, did NOT register VMs"
    end
  end
end

opts :eval_api_perf do
  summary "Measures API performance of various VSAN Mgmt APIs"
  arg :hosts_and_clusters, nil, :lookup => [VIM::HostSystem, VIM::ClusterComputeResource], :multi => true
  opt :exclude_cmmds_queries, "Exclude CMMDS queries", :type => :boolean
  opt :hdd_uuid, "HDD UUID to test QueryObjectsOnPhysicalVsanDisk() against", :type => :string
end

def _measure_perf(title)
  times = []
  (1..3).each do |i|
    t1 = Time.now
    yield
    t2 = Time.now
    times << (t2 - t1)
  end
  puts "#{Time.now}: #{title} took %.2f/%.2f/%.2f seconds" % times
end

def eval_api_perf hosts_and_clusters, opts = {}
  conn = hosts_and_clusters.first._connection
  hosts = hosts_and_clusters.select{|x| x.is_a?(VIM::HostSystem)}
  clusters = hosts_and_clusters.select{|x| x.is_a?(VIM::ClusterComputeResource)}
  pc = conn.propertyCollector
  cluster_hosts = pc.collectMultiple(clusters, 'host')
  cluster_hosts.each do |cluster, props|
    hosts += props['host']
  end
  hosts = hosts.uniq

  hosts_props = pc.collectMultiple(hosts,
  'name',
  'runtime.connectionState',
  'configManager.vsanSystem',
  'configManager.vsanInternalSystem',
  'vm'
  )

  hosts = hosts_props.select do |k,v|
    v['runtime.connectionState'] == 'connected'
  end.keys
  if hosts.length == 0
    err "Couldn't find any connected hosts"
  end

  hosts_vsansys = Hash[hosts_props.map{|k,v| [v['configManager.vsanSystem'], k]}]
  node_uuids = pc.collectMultiple(hosts_vsansys.keys, 'config.clusterInfo.nodeUuid')
  node_uuids = Hash[node_uuids.map do |k, v|
    [v['config.clusterInfo.nodeUuid'], hosts_vsansys[k]]
  end]

  lock = Mutex.new
  host = hosts.first
  vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
  hostname = hosts_props[host]['name']
  vms = hosts.map{|x| hosts_props[x]['vm']}.flatten
  puts "#{Time.now}: Measuring against host #{hostname}"
  puts "#{Time.now}: Number of hosts: #{hosts.length}"
  puts "#{Time.now}: Number of VMs: #{vms.length}"

  host.ssh do |ssh|
    objs = ssh.exec!("cmmds-tool find -t DOM_OBJECT | grep Healthy | wc -l").to_i
    comps = ssh.exec!("cmmds-tool find -t LSOM_OBJECT | grep Healthy | wc -l").to_i
    puts "#{Time.now}: Number of objects: #{objs}"
    puts "#{Time.now}: Number of components: #{comps}"
  end

  _measure_perf("query_physical_vsan_disks(with lsom_objects_count)") do
    vsanIntSys.query_physical_vsan_disks(:props => [
      'lsom_objects_count',
      'uuid',
      'isSsd',
      'capacity',
      'capacityUsed',
      'capacityReserved',
      'iops',
      'iopsReserved',
      'owner',
    ])
  end
  _measure_perf("query_physical_vsan_disks(without lsom_objects_count)") do
    vsanIntSys.query_physical_vsan_disks(:props => [
      'uuid',
      'isSsd',
      'capacity',
      'capacityUsed',
      'capacityReserved',
      'iops',
      'iopsReserved',
      'owner',
    ])
  end
  $vsanUseGzipApis = true
  _measure_perf("query_syncing_vsan_objects()") do
    vsanIntSys.query_syncing_vsan_objects()
  end
  if opts[:hdd_uuid]
    _measure_perf("query_objects_on_physical_vsan_disk([#{opts[:hdd_uuid]}])") do
      vsanIntSys.query_objects_on_physical_vsan_disk(:disks => [opts[:hdd_uuid]])
    end
  else
    puts "#{Time.now}: Skipping query_objects_on_physical_vsan_disk. --hdd-uuid not specified"
  end
  # XXX: QueryObjectsOnPhysicalVsanDisk
  if !opts[:exclude_cmmds_queries]
    _measure_perf("query_cmmds(all objects)") do
      vsanIntSys.query_cmmds([{:type => 'DOM_OBJECT'}], :gzip => true)
    end
    _measure_perf("query_cmmds(all config_status)") do
      vsanIntSys.query_cmmds([{:type => 'CONFIG_STATUS'}], :gzip => true)
    end
    _measure_perf("query_cmmds(all components)") do
      vsanIntSys.query_cmmds([{:type => 'LSOM_OBJECT'}], :gzip => true)
    end
  end
end

opts :clear_fault_domains do
  summary "Clear fault domains of all hosts in a cluster."
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
end

def clear_fault_domains cluster_or_host, opts = {}
  conn = cluster_or_host._connection
  pc = conn.propertyCollector
  if cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    hosts = cluster.host
  else
    hosts = [host]
  end

  _run_with_rev(conn, "dev") do
    hosts_props = pc.collectMultiple(hosts,
    'name',
    'runtime.connectionState',
    'configManager.vsanSystem',
    'configManager.vsanInternalSystem'
    )
    connected_hosts = hosts_props.select do |k,v|
      v['runtime.connectionState'] == 'connected'
    end.keys
    host = connected_hosts.first
    if !host
      err "Couldn't find any connected hosts"
    end
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']

    threads = connected_hosts.map do |host|
      Thread.new do
        c1 = conn.spawn_additional_connection
        host2 = host.dup_on_conn(c1)
        host2.esxcli.vsan.faultdomain.reset
      end
    end.each{|t| t.join}
  end
  puts "Done"
end

opts :fault_domains do
  summary "Print component status for objects in the cluster."
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
end

def fault_domains cluster_or_host, opts = {}
  conn = cluster_or_host._connection
  pc = conn.propertyCollector
  if cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    hosts = cluster.host
  else
    hosts = [host]
  end

  _run_with_rev(conn, "dev") do
    hosts_props = pc.collectMultiple(hosts,
    'name',
    'runtime.connectionState',
    'configManager.vsanSystem',
    'configManager.vsanInternalSystem'
    )
    connected_hosts = hosts_props.select do |k,v|
      v['runtime.connectionState'] == 'connected'
    end.keys
    host = connected_hosts.first
    if !host
      err "Couldn't find any connected hosts"
    end
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']

    threads = connected_hosts.map do |host|
      Thread.new do
        c1 = conn.spawn_additional_connection
        host2 = host.dup_on_conn(c1)
        fd = host2.esxcli.vsan.faultdomain.get
        hosts_props[host]['faultDomainName'] = fd.faultDomainName
        hosts_props[host]['faultDomainId'] = fd.faultDomainId
      end
    end.each{|t| t.join}

    t = Terminal::Table.new()
    t << ['Host', 'Fault Domain', 'Fault Domain Id']
    t.add_separator
    hosts.each do |host|
      if hosts_props[host]['runtime.connectionState'] == 'connected'
        fd = hosts_props[host]['faultDomainName']
        id = hosts_props[host]['faultDomainId']
      else
        fd = "(Host not connected)"
        id = "(Host not connected)"
      end
      t << [
        hosts_props[host]['name'],
        fd,
        id
      ]
    end
    puts t
  end
end

class VscsiStatsExecutor
  def initialize vscsiStatsService
    @serv = vscsiStatsService
  end

  def _exec cmd
    @serv.ExecuteSimpleCommand(:arguments => [cmd])
  end

  def _exec_basic cmd
    res = _exec(cmd).strip
    if res != "OK"
      raise "Failed to run #{cmd}: #{res}"
    end
    res
  end

  def start
    _exec_basic("StartVscsiStats")
  end

  def stop
    _exec_basic("StopVscsiStats")
  end

  def reset
    _exec_basic("ResetVscsiStats")
  end

  def getstats
    xml = _exec("FetchAllHistograms")
    xml = Nokogiri(xml)
    vms = xml.xpath("//vscsiStats/VM")
    out = {}
    vms.each do |vm|
      tmp = vm.dup
      tmp.children.reject{|y| y.text?}.each{|y| y.remove}
      vmInfo = Hash[tmp.text.split("\n").map do |line|
        line.split(": ", 2)
      end]

      disks = {}
      vm.xpath("VirtualDisk").each do |disk|
        tmp = disk.dup
        tmp.children.reject{|y| y.text?}.each{|y| y.remove}
        diskInfo = Hash[tmp.text.split("\n").map do |line|
          line.split(": ", 2)
        end]

        histos = {}
        disk.xpath("histo").each do |histo|
          lines = histo.text.strip.split("\n")
          title = lines.shift
          title, descr = title.split(": ", 2)
          title = title.gsub("VSCSIVsi_", "")
          histos[title] = Hash[lines.map{|line| line.split(": ", 2)}]
          histos[title]['limits'] = histos[title]['limits'].split(',')
          histos[title]['counts'] = histos[title]['counts'].split(',')
          histos[title]['numBuckets'] = histos[title]['numBuckets'].to_i
          histos[title]['descr'] = descr

          numBuckets = histos[title]['numBuckets']
          histos[title]['histo'] = Hash[numBuckets.times.map do |i|
            [histos[title]['limits'][i].to_i, histos[title]['counts'][i].to_i]
          end]
        end

        disks[diskInfo['Virtual disk name']] = histos
      end

      out[vmInfo['VC uuid'].gsub("-", "").gsub(" ", "")] = {
        'vmInfo' => vmInfo,
        'disks' => disks
      }
    end
    out
  end
end

opts :vscsi_histograms do
  summary "Print component status for objects in the cluster."
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  arg :vms, nil, :lookup => [VIM::VirtualMachine], :multi => true
end

def vscsi_histograms cluster_or_host, vms, opts = {}
  conn = cluster_or_host._connection
  pc = conn.propertyCollector
  serviceMgr = conn.serviceContent.serviceManager
  vscsiStatsService = serviceMgr.service.find do |x|
    x.serviceName == "VscsiStats"
  end
  if !vscsiStatsService
    err "VscsiStats service not found"
  end
  vscsiStatsService = vscsiStatsService.service

  vms_props = pc.collectMultiple(vms, 'summary.config.instanceUuid')

  srv = VscsiStatsExecutor.new(vscsiStatsService)
  puts "#{Time.now}: Starting vscsi stats collection"
  srv.start

  puts "#{Time.now}: Sleeping for 20 seconds"
  sleep(20)

  puts "#{Time.now}: Fetching histograms"
  vmsStats = srv.getstats
  vms.each do |vm|
    uuid = vms_props[vm]['summary.config.instanceUuid']
    uuid = uuid.gsub("-", "").gsub(" ", "")
    vmStats = vmsStats[uuid]
    if !vmStats
      err "Stats about #{vms_rops[vm]['name']} not in result set"
    end
    vmStats['disks'].each do |disk, histos|
      vmName = vmStats['vmInfo']['VM display name']
      puts "VM '#{vmName}', Disk #{disk}:"
      t = Terminal::Table.new()
      t << ['Name', "Histogram values"]
      histos.each do |histoName, histoInfo|
        t2 = Terminal::Table.new()
        t2 << ['Limit', 'Count']
        t2.add_separator
        histoInfo['histo'].each do |limit, count|
          if limit == 9223372036854775807
            limit = "MAX"
          end
          t2 << [limit, count]
        end
        t.add_separator
        t << [histoName, t2.to_s]
      end
      #puts t

      t = Terminal::Table.new()
      t << ['Name', "Min", "Max", "Mean", "Count"]
      t.add_separator
      histos.each do |histoName, histoInfo|
        t << [
          histoName,
          histoInfo['min'],
          histoInfo['max'],
          histoInfo['mean'],
          histoInfo['count'],
        ]
      end
      puts t
      puts ""
    end
  end

  puts "#{Time.now}: Stopping vscsi stats collection"
  srv.stop
end

if $rvc_vsan_gss_mode
  opts :object_recover_inaccessible do
    summary "Recovery tool for when you have a good component, but no accessibility"
    arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
    arg :obj_uuid, nil, :type => :string
    opt :compute_dest_md5sum, "After the recovery, compute MD5 sum of destination", :type => :boolean
    opt :verbose, "Verbose logging?", :type => :boolean
    opt :policy, "Policy to use when creating dest. object", :type => :string
  end
end

def object_recover_inaccessible cluster_or_host, obj_uuid, opts = {}
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  if cluster_or_host.is_a?(VIM::ClusterComputeResource)
    cluster = cluster_or_host
    hosts = cluster.host
  else
    hosts = [cluster_or_host]
  end

  _run_with_rev(conn, "dev") do
    hosts_props = pc.collectMultiple(hosts,
    'name',
    'runtime.connectionState',
    'configManager.vsanSystem',
    'configManager.vsanInternalSystem'
    )
    connected_hosts = hosts_props.select do |k,v|
      v['runtime.connectionState'] == 'connected'
    end.keys
    host = connected_hosts.first
    if !host
      err "Couldn't find any connected hosts"
    end
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
    vsanSysList = Hash[hosts_props.map do |host, props|
      [host, props['configManager.vsanSystem']]
    end]
    clusterInfos = pc.collectMultiple(vsanSysList.values,
    'config.clusterInfo')
    hostUuidMap = Hash[vsanSysList.map do |host, sys|
      [clusterInfos[sys]['config.clusterInfo'].nodeUuid, host]
    end]
    entries = vsanIntSys.query_cmmds([{
      :uuid => obj_uuid,
      :type => 'DOM_OBJECT',
      }], :gzip => true)
    if !entries[0]
      err "Object #{obj_uuid} couldn't be found"
    end
    obj = entries[0]

    disks = vsanIntSys.query_cmmds([{
      :type => 'DISK',
      }], :gzip => true)
    if !entries[0]
      err "Object #{obj_uuid} couldn't be found"
    end
    diskToHostMap = Hash[disks.map{|x| [x['uuid'], x['owner']]}]

    comps = _components_in_dom_config(obj['content'])
    comps = comps.select{|x| x['type'] == 'Component'}
    comps = comps.select{|x| x['attributes']['componentState'] == 5}
    puts "#{Time.now}: Object #{obj_uuid} has #{comps.length} ACTIVE components"
    if comps.length == 0
      err "No ACTIVE components left"
    end
    diskUuids = comps.map{|x| x['diskUuid']}.uniq
    hostUuids = diskUuids.map{|x| diskToHostMap[x]}.compact.uniq
    if hostUuids.length == 0
      err "Couldn't find host on which components live"
    end
    hostsWithComps = hostUuids.map{|x| hostUuidMap[x]}.compact
    if hostsWithComps.length == 0
      err "Couldn't find host reference on which components live"
    end

    puts "#{Time.now}: Identified the following hosts that have live components:"
    hostsWithComps.each do |h|
      puts "#{Time.now}:   #{hosts_props[h]['name']}"
    end

    host = hostsWithComps.first
    hostname = hosts_props[host]['name']
    puts "#{Time.now}: Starting with first host #{hostname}"
    runRecoveryTool = nil
    dstObjUuid = nil
    size = nil
    _MB = 1024**2
    _GB = 1024**3
    incrementsInMB = 1000
    objExtAttr = nil
    host.ssh do |ssh|
      params = [
        "--source-uuid #{obj_uuid}",
        "--create-destination-object",
      ]
      if opts[:policy]
        params << "--policy '#{opts[:policy]}'"
      end

      runRecoveryTool = Proc.new() do |ssh, params|
        resultFilename = "/root/recovery.#{obj_uuid}.result"
        bin = "source /.profile; python $VMTREE/support/scripts/vsan/recoverInaccessibleObjects.py"
        cmd = "#{bin} --result-json #{resultFilename} #{params.join(' ')}"
        if opts[:verbose]
          puts "#{Time.now}: Running '#{cmd}' on #{hostname}"
        end
        # XXX: Check error code
        out = ssh.exec!(cmd)
        if opts[:verbose]
          puts out
        end
        result = ssh.scp.download!(resultFilename)
        result = JSON.load(result)
      end

      recoverRange = Proc.new do |ssh, startOffset, endOffset|
        params = [
          "--source-uuid #{obj_uuid}",
          "--dest-uuid #{dstObjUuid}",
          "--start-offset #{startOffset}",
          "--end-offset #{endOffset}",
        ]
        if !objExtAttr
          params << "--include-extattr"
        end
        result = runRecoveryTool.call(ssh, params)
        if opts[:verbose]
          pp result
        end
        if result['objExtAttr']
          objExtAttr = JSON.load result['objExtAttr']
        end
      end

      recoverFull = Proc.new do |ssh|
        offset = 0
        while offset < size
          length = [incrementsInMB * _MB, size - offset].min
          t1 = Time.now
          recoverRange.call(ssh, offset, offset + length)
          duration = Time.now - t1

          puts "#{Time.now}: %s: Took %.2f sec to transfer %d MB (%.2f MB/s)" % [
            hostname,
            duration,
            (length / _MB).to_i,
            length / _MB / duration
          ]
          offset += length
        end
      end

      result = runRecoveryTool.call(ssh, params)
      dstObjUuid = result['uuid']
      size = result['size']
      puts "#{Time.now}: Destination object created with UUID #{dstObjUuid}"
      puts "#{Time.now}: Object size is: %.2f GB" % [size.to_f / 1024**3]

      recoverFull.call(ssh)

      otherHosts = hostsWithComps - [host]
      otherHosts.each do |otherHost|
        hostname = hosts_props[otherHost]['name']
        puts "#{Time.now}: Doing recovery of components host #{hostname}"
        otherHost.ssh do |ssh|
          recoverFull.call(ssh)
        end
      end

      if opts[:compute_dest_md5sum]
        hostname = hosts_props[host]['name']
        cmds = [
          "/usr/lib/vmware/osfs/bin/objtool open -u #{dstObjUuid}",
          "md5sum /vmfs/devices/vsan/#{dstObjUuid}",
        ]
        puts ssh.exec!(cmds.join("; "))
      end
    end # host.ssh

    puts ""
    if objExtAttr
      puts "#{Time.now}: Additonal information about recovered object #{obj_uuid}:"
      puts "#{Time.now}:   Object type: #{objExtAttr['Object class']}"
      puts "#{Time.now}:   Object path: #{objExtAttr['Object path']}"
      if objExtAttr['Object class'] == "vmnamespace"
        puts "#{Time.now}:   User friendly name: #{objExtAttr['User friendly name']}"
      end
    end
    puts ""
    puts "#{Time.now}: Done: New object #{dstObjUuid} has the data we were able to recover"
  end
end

def _read_lsom_component_md5_range host, compUuid, offset, length
  Net::SSH.start(host, 'root', :password => 'cashc0w') do |ssh|
    res = ssh.run_python_file(
    "/vsan-vsi.py",
    "ReadLsomComponentMd5Range #{compUuid} #{offset} #{length}"
    )
    return res
  end
end

def _do_compare_yyy offset, size
  host1 = 'w3-vsan-esx019.eng.vmware.com'
  host2 = 'w3-vsan-esx020.eng.vmware.com'
  compUuid1 = 'f4b38b53-367e-ed30-3ac1-90b11c4fda9f'
  compUuid2 = 'a3756353-e438-2a0a-bdf1-90b11c4fda9f'

  sliceLen = 1 * 1024**3 # 1GB
  while offset < size
    puts "Offset: #{offset} (%.2f GB)" % [offset / 1024**3]
    if !_do_compare_once(host1, compUuid1, host2, compUuid2, offset, sliceLen)
      puts "Failed at offset: %u" % offset
    end
    offset += sliceLen
  end
end

def _do_compare_once host1, compUuid1, host2, compUuid2, offset, length

  acceptedSlices = []
  (0..3).each do |i|
    md5_1 = nil
    md5_2 = nil
    threads = []
    threads << Thread.new do
      md5_1 = _read_lsom_component_md5_range(host1, compUuid1, offset, length)
    end
    threads << Thread.new do
      md5_2 = _read_lsom_component_md5_range(host2, compUuid2, offset, length)
    end
    threads.each{|t| t.join}
    md5_1.keys.each do |slice|
      if acceptedSlices.member?(slice)
        next
      end
      if md5_1[slice] == md5_2[slice]
        acceptedSlices << slice
      end
    end
    if acceptedSlices.length == md5_1.keys.length
      return true
    end
    puts "Not all slices were accepted (#{acceptedSlices.length} < #{md5_1.keys.length})"
  end
  false
end

opts :host_debug_multicast do
  summary "Debug multicast"
  arg :hosts, nil, :lookup => [VIM::HostSystem], :multi => true
  opt :password, "ESX Password", :type => :string
  opt :vmknic, "vmknic name", :type => :string, :required => true
  opt :cluster_uuid, "Filter by this cluster UUID", :type => :string
  opt :duration, "Duration to watch for packets. 4 minutes is recommend", :type => :int, :default => 4 * 60
  opt :no_agenthb, "Don't display Agent heartbeats", :type => :boolean
end

def host_debug_multicast hosts, opts
  puts "#{Time.now}: Gathering information about hosts and VSAN"
  conn = hosts.first._connection
  pc = conn.propertyCollector
  hosts_props = pc.collectMultiple(hosts,
  'name',
  'configManager.vsanSystem',
  'configManager.vsanInternalSystem'
  )
  hosts_vsanprops = pc.collectMultiple(
  hosts.map{|h| hosts_props[h]['configManager.vsanSystem']},
  'config.clusterInfo',
  'config.networkInfo'
  )
  nodeUuidToHostMap = Hash[hosts.map do |h|
    vsanSys = hosts_props[h]['configManager.vsanSystem']
    clusterInfo = hosts_vsanprops[vsanSys]['config.clusterInfo']
    [clusterInfo.nodeUuid, h]
  end]

  lock = Mutex.new
  allPackets = {}
  hostStarttime = {}
  startTime = Time.now.to_f

  chars = ('A'..'Z').to_a + ('1'..'9').to_a
  hostChars = {}
  hosts = hosts.sort_by{|host| hosts_props[host]['name']}
  hosts.each_with_index do |host, i|
    hostChars[host] = chars[i]
    puts "#{Time.now}: #{chars[i]} = Host #{hosts_props[host]['name']}"
  end

  duration = opts[:duration]
  puts "#{Time.now}: Watching packets for #{duration} seconds"
  latestStarttime = []
  hostPackets = {}
  timestr = Time.now.strftime('%Y-%m-%d.%H-%M-%S')
  tmpdir = Dir.mktmpdir("rvc-multicast-tcpdump-#{timestr}")
  hosts.map do |host|
    Thread.new do
      host.ssh do |ssh|
        hostname = hosts_props[host]['name']
        res = ssh.run_python_file(
        "/vsan-vsi.py",
        "WatchMulticastPackets '#{opts[:vmknic]}' '#{duration.to_f}'",
        :gzip => true
        )

        filename = File.join(tmpdir, "tcpdump-#{hostname}-#{opts[:vmknic]}.pcap")
        open(filename, 'w') do |io|
          io.write(Base64.decode64(res['pcap']))
        end

        diff = startTime - res['calltime']
        pkts = res['pkts'].each do |p|
          p['normTs'] = p['timestamp'] + diff
          p['host'] = host
          if p['pktType'] == 'cmmds'
            # Multicast packets should be deduped using this key
            p['key'] = [
              p['pktType'], p['srcIp'], p['srcUuid'],
              p['dstIp'], p['msgType'], p['cmmdsMcastSeq']
            ].join("-")
          elsif p['pktType'] == 'igmp'
            # Every packet should be unique
            p['key'] = [
              p['pktType'], p['srcIp'], p['timestamp'],
              p['dstIp'], p['msgType'], p['igmpGA']
            ].join("-")
          end
        end
        lock.synchronize do
          puts "#{Time.now}: Wrote pcap capture of #{hostname} to #{filename}"
          hostPackets[host] = pkts
        end
      end
    end
  end.each{|t| t.join}

  puts "#{Time.now}: Got observed packets from all hosts, analysing"

  hostPackets.each do |host, pkts|
    pkts.each do |p|
      allPackets[p['key']] ||= {
        'pkts' => [],
        'timestamp' => p['normTs']
      }
      allPackets[p['key']]['pkts'] << p
    end
  end

  metapackets = allPackets.values.sort_by{|x| x['timestamp']}
  timestamps = metapackets.map{|x| x['timestamp']}
  minTs = timestamps.min
  maxTs = timestamps.max
  # Remove first and last seconds to remove noise due to non perfect
  # alignment of tcpdump runs
  slack = 2
  metapackets = metapackets.select do |x|
    (x['timestamp'] > minTs + slack) && (x['timestamp'] < maxTs - slack)
  end

  metapackets.each do |info|
    pkts = info['pkts']
    hosts = pkts.map{|x| x['host']}
    hostRecvStr = ""
    hostChars.each do |host, char|
      if hosts.member?(host)
        hostRecvStr += char
      else
        hostRecvStr += " "
      end
    end

    # cmmdsPkts = pkts.select{|x| }
    # if opts[:cluster_uuid]
    # cmmdsPkts = cmmdsPkts.select{|x| x['clusterUuid'] == opts[:cluster_uuid]}
    # end
    #
    # masterPkts = cmmdsPkts.select{|x| x['msgType'] == 'MASTER_HEARTBEAT'}
    # agentPkts = cmmdsPkts.select{|x| x['msgType'] == 'AGENT_HEARTBEAT'}
    pkt = pkts.first
    pkt['normTsStr'] = "%.2f" % pkt['normTs']
    if pkt['pktType'] == 'cmmds'
      if opts[:no_agenthb] && pkt['msgType'] == 'AGENT_HEARTBEAT'
        next
      end

      srcHost = nodeUuidToHostMap[pkt['srcUuid']]
      if srcHost
        srcHost = hosts_props[srcHost]['name']
      else
        srcHost = pkt['srcUuid']
      end
      str = "%s: %26s (#%08d) from:%s(%s) to:%s" % [
        pkt['normTsStr'],
        pkt['msgType'],
        pkt['cmmdsMcastSeq'],
        pkt['srcIp'], srcHost,
        pkt['dstIp'],
      ]
    elsif pkt['pktType'] == 'igmp'
      igmp = pkt
      str = "#{igmp['normTsStr']}: #{igmp['msgType']} - GA: #{igmp['igmpGA']}"
    end

    puts "[#{hostRecvStr}] #{str}"

    # seenHosts = cmmdsPkts.map{|x| x['srcIp']}.uniq
    # seenHostsUuid = cmmdsPkts.map{|x| x['srcUuid']}.uniq
    # seenMasters = masterPkts.map{|x| x['srcIp']}.uniq
    # seenMastersUuid = masterPkts.map{|x| x['srcUuid']}.uniq
    # seenAgents = agentPkts.map{|x| x['srcIp']}.uniq
    # seenAgentsUuid = agentPkts.map{|x| x['srcUuid']}.uniq
    # puts "Recognized %d CMMDS messages" % [cmmdsPkts.length]
    # puts "Seen hosts (%s): %s" % [seenHosts.length, seenHosts]
    # puts "Seen hosts UUIDs (%s): %s" % [seenHostsUuid.length, seenHostsUuid]
    # puts "Seen masters (%s): %s" % [seenMasters.length, seenMasters]
    # puts "Seen masters UUIDs (%s): %s" % [seenMastersUuid.length, seenMastersUuid]
    # puts "Seen agents (%s): %s" % [seenAgents.length, seenAgents]
    # puts "Seen agents UUIDs (%s): %s" % [seenAgentsUuid.length, seenAgentsUuid]
    #
    #igmps = pkts.select{|x| x['pktType'] == 'igmp'}
    #igmps.each do |igmp|
    #  puts "#{igmp['normTs']}: #{igmp['msgType']} - GA: #{igmp['igmpGA']}"
    #end
  end
end

opts :host_advcfg_set do
  summary "Set advanced config option"
  arg :hosts, nil, :lookup => [VIM::HostSystem], :multi => true
  opt :option, "Option", :type => :string
  opt :int_value, "Integer value", :type => :int
  opt :string_value, "String value", :type => :string
end

def host_advcfg_set hosts, opts
  values = [opts[:int_value], opts[:string_value]]
  if values.select{|x| x != nil}.length == 0
    err "Supply a value"
  end
  if values.select{|x| x != nil}.length > 1
    err "Supply only one value type"
  end
  value = values.find{|x| x != nil}
  conn = hosts.first._connection
  pc = conn.propertyCollector
  hosts_props = pc.collectMultiple(hosts,
  'name',
  'configManager.advancedOption'
  )
  hosts.each do |host|
    hostname = hosts_props[host]['name']
    puts "Updating config option on #{hostname}"
    optMgr = hosts_props[host]['configManager.advancedOption']
    optMgr.UpdateOptions(
    :changedValue => [VIM::OptionValue({
      :key => opts[:option], :value => value
      })]
    )
  end
end

# check hosts' status before evacuation operation,
# 1. we don't want to send request to disconnected host,
# 2. only v6.0 and above hosts have evacuation node feature,
# 3. node evacuation can only be requested to VSAN node,
# 4. and node already evacuated shouldn't be evacuated again.
#
# hosts: Array of VIM::HostSystem, hosts which will be evacuated/recomissioned,
# evacuation: true to evacuation node,
#             false to exit evacuation.
def _update_nodes_evacuation_status hosts, evacuation = true
  conn = hosts.first._connection
  pc = conn.propertyCollector
  hosts_props = pc.collectMultiple(hosts,
  'name',
  'runtime.connectionState',
  'config.product',
  'configManager.vsanSystem',
  'configManager.vsanInternalSystem'
  )
  disconnected_hosts = hosts_props.select do |k, v|
    v['runtime.connectionState'] != 'connected'
  end.keys
  if disconnected_hosts.length > 0
    puts "Following hosts are not connected. Operation "
    puts "cannot proceed unless specified hosts are connected "
    puts "to VC. Please fix situation and restart."
    puts "Hosts that are not connected:"
    disconnected_hosts.each do |host|
      puts hosts_props[host]['name']
    end
    return
  end

  mismatch_version = hosts_props.select do |k, v|
    v['config.product'].version < '6.0.0'
  end.keys
  if mismatch_version.length > 0
    puts "Detected hosts that aren't running 6.0 or above, "
    puts "Operation has been halted. Please make sure all "
    puts "specified hosts are running 6.0 or above, and restart."
    puts "Hosts that are not running 6.0 or above:"
    mismatch_version.each do |host|
      puts hosts_props[host]['name']
    end
    return
  end

  vsan_disabled = {}
  mismatch_decom_state = {}
  # decom_state 0 indicates NOT_DECOMMISSIONED
  # decom_state 6 indicates DECOMMISSIONED
  expected_decom_state = evacuation ? 0 : 6
  hosts.map do |host|
    Thread.new do
      begin
        c1 = conn.spawn_additional_connection
        vsanSys = hosts_props[host]['configManager.vsanSystem']
        vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
        vsanSys2 = vsanSys.dup_on_conn(c1)
        vsanIntSys2 = vsanIntSys.dup_on_conn(c1)
        if vsanSys2.config.enabled
          host_status = vsanSys2.QueryHostStatus()
          decom_state = vsanIntSys2.query_cmmds([
            {:type => 'NODE_DECOM_STATE', :uuid => host_status.nodeUuid}
          ])
          if !decom_state ||
          !decom_state[0] ||
          decom_state[0]['content']['decomState'] != expected_decom_state
            mismatch_decom_state[host] = true
          end
        else
          vsan_disabled[host] = true
        end
      rescue Exception => ex
        mismatch_decom_state[host] = true
      end
    end
  end.each{|t| t.join}
  if vsan_disabled.length > 0
    puts "Detected hosts that don't enable VSAN, operation has "
    puts "been halted. Only host with VSAN enabled is allowed."
    puts "Please fix this and try again."
    puts "Hosts that don't enable VSAN:"
    vsan_disabled.keys.each do |host|
      puts hosts_props[host]['name']
    end
    return
  end

  if mismatch_decom_state.length > 0
    current_decom_state = evacuation ? 'not decommissioned' : 'decommissioned'
    puts "Following hosts are not in expected evacuation state,"
    puts "Operation has been halted. Expected evacuation state is:"
    puts "#{current_decom_state}, please fix this and try again."
    puts "Hosts with unexpected evacuation state:"
    mismatch_decom_state.keys.each do |host|
      puts hosts_props[host]['name']
    end
    return
  end
  return hosts_props
end

# helper to evacuate VSAN node, or exit the evacuation status.
def _node_evacuation hosts, evacuation = true, opts = {}
  conn = hosts.first._connection
  hosts = hosts.uniq

  # precheck for specified hosts
  hosts_props = _update_nodes_evacuation_status(hosts, evacuation)
  if !hosts_props
    return
  end

  vsan_mode = 'evacuateAllData'
  time_out = 0
  if opts[:no_action]
    vsan_mode = 'noAction'
  end
  if opts[:allow_reduced_redundancy]
    vsan_mode = 'ensureObjectAccessibility'
  end
  puts "#{Time.now}: Data evacuation mode #{vsan_mode}" if evacuation
  puts "#{Time.now}: Data evacuation time out #{opts[:time_out]}" if evacuation
  puts ""
  op = evacuation ? "evacuate data" : "exit evacuation"
  _run_with_rev(conn, 'dev') do
    hosts.each do |host|
      host_name = hosts_props[host]['name']
      results = {}
      task = nil
      begin
        vsanSys = hosts_props[host]['configManager.vsanSystem']
        puts "#{Time.now}: Start to #{op} for host #{host_name}"
        if evacuation
          task = vsanSys.EvacuateVsanNode_Task(
          :maintenanceSpec => {
            :vsanMode => {
            :objectAction => vsan_mode,
            },
          },
          :timeout => opts[:time_out]
          )
          results = progress([task])
        else
          task = vsanSys.RecommissionVsanNode_Task()
          results = progress([task])
        end
        if task && !results.empty?
          result = results[task]
          if result.is_a?(VIM::LocalizedMethodFault)
            puts "#{Time.now}: Failed to #{op} for host #{host_name}, #{result.localizedMessage}"
          else
            puts "#{Time.now}: Done #{op} for host #{host_name}"
          end
        end
      rescue Exception => ex
        puts "#{Time.now}: Failed to #{op} for host #{host_name}; #{ex.class}: #{ex.message}"
      end
      puts ""
      if evacuation
        puts "Hosts remain evacuation state until explicily exit evacuation"
        puts "through command vsan.host_exit_evacuation"
      end
    end
  end
end

opts :host_evacuate_data do
  summary "Evacuate hosts from VSAN cluster"
  arg :hosts, nil, :lookup => [VIM::HostSystem], :multi => true
  opt :allow_reduced_redundancy, "Removes the need for nodes worth of free space, by allowing reduced redundancy", :type => :boolean
  opt :no_action, "Do not evacuate data during host evacuation", :type => :boolean
  opt :time_out, "Time out for single node evacuation", :type => :int, :default => 0
end

def host_evacuate_data hosts, opts
  _node_evacuation(hosts, true, opts)
end

opts :host_exit_evacuation do
  summary "Exit hosts' evacuation, bring them back to VSAN cluster as data containers"
  arg :hosts, nil, :lookup => [VIM::HostSystem], :multi => true
end

def host_exit_evacuation hosts
  _node_evacuation(hosts, false)
end

opts :host_wipe_non_vsan_disk do
  summary ""
  arg :hosts, nil, :lookup => [VIM::HostSystem], :multi => true
  opt :disk, "Disk to be wiped clean (multiple allowed)", :type => :string, :multi => true, :required => true
  opt :force, "Do it for real", :type => :boolean
end

def host_wipe_non_vsan_disk hosts, opts
  conn = hosts.first._connection
  pc = conn.propertyCollector
  hosts_info = _collect_disks_info(hosts, opts)
  hosts.each do |host|
    host_info = hosts_info[host]
    host_props = host_info['host_props']
    host_name = host_props['name']
    if hosts.length > 0
      puts "Disks on host #{host_name}:"
    end

    if host_props['runtime.connectionState'] != 'connected'
      puts "  #{host_name} is not connected, skipping"
      next
    end
    dsListProps = host_info['dsListProps']

    disks = host_info['disks'].select do |disk|
      opts[:disk].member?(disk.disk.canonicalName)
    end
    disks.each do |disk|
      puts "Disk: #{disk.disk.displayName}"
      makemodel = [
        disk.disk.vendor,
        disk.disk.model
      ].compact.map{|x| x.strip}.join(" ")
      capacity = disk.disk.capacity
      size = capacity.block * capacity.blockSize
      puts "  Make/Model: #{makemodel}"
      puts "  Type: #{disk.disk.ssd ? "SSD" : "HDD"}"
      puts "  Size: #{size / 1024**3} GB"
      if disk.state == 'inUse'
        puts "  Detected to be a VSAN disk, skipping"
        puts ""
        next
      end
      puts "  Partition table: "
      disk['partition'].each do |x|
        partSize = x.Size.to_f / 1024**3
        type = x['typeStr']
        str = "    #{x.Partition}: %.2f GB, type = #{type}" % partSize
        if type == "vmfs"
          vmfsStr = x['vmfsDs'].map do |vmfsDs|
            "'#{dsListProps[vmfsDs]['name']}'"
          end.join(", ")
          if vmfsStr
            str += " (#{vmfsStr})"
          end
        end
        puts str
      end
      proceed = _questionnaire(
      "Are you sure you want to delete all partitions? [y/N]",
      ['y', 'n'],
      'y'
      )
      if proceed
        if opts[:force]
          puts "Attempting to delete all partitions ..."
          storSys = host_props['configManager.storageSystem']
          storSys.UpdateDiskPartitions(
          :devicePath => disk.disk.devicePath,
          :spec => {}
          )
          puts "Done"
        else
          puts "Would have deleted all partitions and all data, but"
          puts "didn't. Run with --force to delete partitions and "
          puts "eraze all data on disk #{disk.disk.canonicalName} for real."
        end
      end
      puts ""
    end
  end

end

def _questionnaire question, answers, expect_answer
  input = nil
  answers = answers.uniq
  begin
    puts question
    input = $stdin.gets.chomp
    answer = answers.find{|a| input.casecmp(a) == 0}
  end while !answer
  return input.casecmp(expect_answer) == 0
end

opts :host_claim_intel_s3500_as_hdd do
  summary ""
  arg :hosts, nil, :lookup => [VIM::HostSystem], :multi => true
end

def host_claim_intel_s3500_as_hdd hosts, opts = {}
  conn = hosts.first._connection
  pc = conn.propertyCollector
  hosts_info = _collect_disks_info(hosts, opts)
  hosts.each do |host|
    host_info = hosts_info[host]
    host_props = host_info['host_props']
    host_name = host_props['name']
    if hosts.length > 0
      puts "Disks on host #{host_name}:"
    end

    if host_props['runtime.connectionState'] != 'connected'
      puts "  #{host_name} is not connected, skipping"
      next
    end
    dsListProps = host_info['dsListProps']

    disks = host_info['disks'].select do |disk|
      disk.disk.model =~ /^INTEL SSDSC2BB/
    end
    st = host.esxcli.storage
    rule = st.nmp.satp.rule
    claim = st.core.claiming
    disks.each do |disk|
      puts "Claiming #{disk.disk.displayName} as HDD ..."
      dev = disk.disk.canonicalName
      rules = rule.list(:satp => "VMW_SATP_LOCAL").select do |r|
        r.Device == dev && ["disable_ssd", "enable_ssd"].member?(r.Options)
      end.map{|x| x.Options}
      if rules.member?('enable_ssd')
        puts "  Found existing rule to force SSD, clearing ..."
        rule.remove(
        :satp => "VMW_SATP_LOCAL",
        :device => dev,
        :option => 'enable_ssd'
        )
      end
      if !rules.member?('disable_ssd')
        puts "  No existing rule to force HDD, adding ..."
        rule.add(
        :satp => "VMW_SATP_LOCAL",
        :device => dev,
        :option => 'disable_ssd'
        )
      end

      puts "  Refreshing state"
      claim.reclaim(:device => dev)
    end
  end
end
