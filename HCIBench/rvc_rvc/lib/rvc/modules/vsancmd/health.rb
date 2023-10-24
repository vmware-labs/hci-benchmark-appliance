require 'rbvmomi'
require 'rvc/vim'
require 'rvc/lib/vsanhealth'

db = VIM.loader.instance_variable_get(:@db)
db['VimClusterVsanVcClusterHealthSystem'] = db['VsanVcClusterHealthSystem']
db['VimHostVsanHealthSystem'] = db['HostVsanHealthSystem']
db = nil

# This should be moved into core RVC, but as the health system is an
# add on which requires this feature (passing in a cookie via ENV) we
# have to define a new URI scheme here.
RVC::SCHEMES['vimhealth'] = Proc.new do |uri, opts|
  newOpts = {:cookie => ENV['RVC_RBVMOMI_COOKIE']}
  newOpts.merge!(opts || {})
  $shell.cmds[:vim].slate.connect(uri, newOpts)
end


def catch_vim_vsanfault
  begin
    yield
  rescue VIM::VsanFault => fault
    puts 'Error: ' + fault.faultMessage.map{|x| x.message}.join("\n")
  end
end

# in version U2, health is an inbox module of vsphere
# user don't need to install health separately
# so we can comment this command
# if in the futuren health is in async mode, we can re-opened this api

#opts :cluster_install do
#  summary "Installs ESX extensions on Cluster"
#  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
#  opt :dry_run, "Only run installation checks", :type => :boolean
#  opt :force, "Skip any questions, and proceed", :type => :boolean
#end

#def cluster_install clusters, opts = {}
#  install_feature_on_clusters(clusters, 'health', opts)
#end

opts :cluster_status do
  summary "Checks status of ESX extensions on Cluster"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
end

def cluster_status clusters, opts = {}
   cluster_feature_status(clusters, 'health', opts)
end

opts :hcl_update_db do
  summary "Updates the DB, from local file, URL or vmware.com (default)"
  arg :conn, "Path to VC connection like '/<VC>'", :lookup => [VIM], :multi => true
  opt :local_file, "Path to local file that contains DB", :type => :string
  opt :url, "Path to URL that contains DB", :type => :string
  opt :force, "Skip any questions, and proceed", :type => :boolean
end

def hcl_update_db conns, opts = {}
  if opts[:local_file] && opts[:url]
    err "Can't use both --local-file and --url"
  end
  if opts[:local_file]
    puts "#{Time.now}: Updating DB from local file '#{opts[:local_file]}'."
  elsif opts[:url]
    puts "#{Time.now}: Updating DB from URL '#{opts[:url]}'."
    puts "#{Time.now}: Note: vCenter needs to have access to this URL."
  else
    puts "#{Time.now}: Updating DB from vmware.com."
    puts "#{Time.now}: Note: vCenter needs to have access to vmware.com."
  end
  if opts[:force]
    proceed = true
  else
    proceed = _questionnaire(
      "Proceed? [Yes/No]",
      ["yes", "no"],
      "yes"
    )
  end
  if !proceed
    err "Aborted"
  end
  catch_vim_vsanfault do
    if opts[:local_file]
      db = open(opts[:local_file], 'r').read()
      require 'base64'
      io = StringIO.new("")
      z = Zlib::GzipWriter.new(io)
      z.write db
      z.close
      db = Base64.encode64(io.string)

      puts "#{Time.now}: Uploading gzipped DB with size %.3fKB" % (db.length / 1024.0)
      conns.each do |conn|
        vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')
        vvchs.VsanVcUploadHclDb(:db => db)
      end
    else
      conns.each do |conn|
        vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')
        vvchs.VsanVcUpdateHclDbFromWeb(
          :url => opts[:url]
        )
      end
    end
    puts "#{Time.now}: Done"
  end
end


def _questionnaire question, answers, expect_answer
  if !$interactive
    # in non-interactive mode, we take negative answer
    # as user input, because we cannot say 'yes' on behalf
    # of end user.
    return false
  end
  input = nil
  answers = answers.uniq
  begin
    puts question
    input = $stdin.gets.chomp
    answer = answers.find{|a| input.casecmp(a) == 0}
  end while !answer
  return input.casecmp(expect_answer) == 0
end

opts :cluster_attach_to_sr do
  summary "Attach vSAN support bundle to customer service request (SR)"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
  opt :sr, "SR number", :type => :int, :required => true
end

def _getLatestAttachToSrResult cluster, vvchs, taskId
  result = vvchs.VsanQueryAttachToSrHistory(
    'cluster' => cluster,
    'taskId' => taskId
  )
  if result.size > 0
    return result[0]
  else
    RVC::Util.err "No attach to sr result found!"
  end
end

def cluster_attach_to_sr clusters, opts = {}
  if !opts[:sr]
    err "Need to input service request number"
  else
    puts "vSAN Support Assistant performs automated upload"
    puts "of support bundles, and so does not allow you to review,"
    puts "obfuscate or otherwise edit the contents of your support"
    puts "data prior to it being sent to VMware. If your support data"
    puts "may contain regulated data, such as personal, health care data"
    puts "and/or financial data, you should instead use the more manual"
    puts "workflow by clicking vCenter -> Actions -> Export System Logs"
    puts "selecting 'Include vCenter Server' as well as all ESX hosts"
    puts "in the cluster. Follow VMware KB 2072796 "
    puts "(http://kb.vmware.com/kb/2072796) for the manual workflow. "
    puts "This process may take a moment ..."
    puts ""
  end

  conn = clusters.first._connection
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')
  tasks = []
  clusters.each do |cluster|
    begin
      name = cluster.name
      puts "Attaching vSAN support bundle for the cluster '#{name}' ..."
      task = vvchs.VsanAttachVsanSupportBundleToSr(
        :cluster => cluster,
        :srNumber => opts[:sr]
      )
      tasks << VIM::Task(conn, task._ref)
    end
  end
  progress(tasks)

  clusters.zip(tasks).each do |cluster, task|
    begin
      result = _getLatestAttachToSrResult(cluster, vvchs, task._ref)
      if result.success
        puts "Support bundle is uploaded successfully for the cluster #{cluster.name}"
      else
        puts "Issues found to upload support bundle for the cluster #{cluster.name}"
      end
    end
  end

end

opts :cluster_proxy_status do
  summary "Get proxy configuration status for vSAN health service"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
end

def cluster_proxy_status clusters, opts = {}
  conn = clusters.first._connection
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')
  t = Terminal::Table.new()
  t << ['Cluster', 'Proxy Host', 'Proxy Port', 'Proxy User']
  t.add_separator
  clusters.each do |cluster|
    begin
      name = cluster.name
      config = vvchs.VsanHealthQueryVsanClusterHealthConfig(
        :cluster => cluster
      )
      t << [name, config.vsanTelemetryProxy.host, config.vsanTelemetryProxy.port, config.vsanTelemetryProxy.user]
    end
  end
  puts t
end

opts :cluster_proxy_configure do
  summary "Configure the proxy to access the internet when you use vSAN CEIP(Customer Experience Improvement Program), vSAN Support Assistant and get latest HCL database online."
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
  opt :host, "Proxy host", :type => :string
  opt :port, "Proxy port", :type => :int
  opt :user, "Proxy user", :type => :string
end

def cluster_proxy_configure clusters, opts = {}
  # we need to check the host and port, if both host and port are existing
  # and then we can check the user parameter
  if opts[:host] && opts[:port]
    op = "Configure"
  elsif !opts[:host] && !opts[:port] && !opts[:user]
    op = "Remove"
  else
    if !opts[:host] || !opts[:port]
      if !opts[:host] && !opts[:port]
        err "missing arguments 'host' and 'port'"
      elsif !opts[:host]
        err "missing argument 'host'"
      elsif !opts[:port]
        err "missing argument 'port'"
      end
      return
    end
  end

  #We only allow user to set proxy password in interactive mode
  # For non-interactive mode, we dont' support now and will throw exception
  pass = nil
  if opts[:user]
    if !$interactive
      raise "Cannot support configuring proxy in non interactive mode"
    end
    pass = ask("Enter proxy password (empty for no password): ") { |q| q.echo = false }
    pass1 = ask("Enter proxy password again: ") { |q| q.echo = false }
    if pass != pass1
      err "You entered different password!"
    elsif pass.length == 0
       pass = nil
    end
    puts ""
  end

  conn = clusters.first._connection
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')
  clusters.each do |cluster|
    begin
      name = cluster.name
      puts "#{op} the proxy for the cluster '#{name}' ..."
      vvchs.VsanHealthSetVsanClusterTelemetryConfig(
        :cluster => cluster,
        :vsanClusterHealthConfig => {
          :vsanTelemetryProxy => {
              :host => opts[:host],
              :port => opts[:port],
              :user => opts[:user],
              :password => pass
          }
        }
      )
    end
  end

end

opts :cluster_repair_immediately do
  summary "Triggers immediate repair of objects waiting for an event"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
end

def cluster_repair_immediately clusters, opts = {}
  puts "This command will trigger the immediate repair of objects that"
  puts "are waiting on one of two events. The first category of objects"
  puts "are impacted by components in ABSENT state (caused by failed"
  puts "hosts or hot-unplugged drives). vSAN will wait 60 minutes by "
  puts "default as in most such cases the failed components will come"
  puts "back. The second category of objects was not repaired previously"
  puts "because under the cluster conditions at the time it wasn't "
  puts "possible. vSAN will periodically recheck those objects."
  puts "Both types of objects will be instructed to attempt a repair"
  puts "immediately. This process may take a moment ..."
  puts ""
  conn = clusters.first._connection
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')
  tasks = []
  clusters.each do |cluster|
    begin
      task = vvchs.VsanHealthRepairClusterObjectsImmediate(
        :cluster => cluster)
      tasks << VIM::Task(conn, task._ref)
    end
  end
  progress(tasks)
end

opts :cluster_rebalance do
  summary "Rebalance the vSAN cluster"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
end

def cluster_rebalance clusters, opts = {}
  puts "This command will trigger the immediate rebalance of vSAN"
  puts "cluster. It will rebalance the vSAN objects for the imbalance hosts"
  puts "based on the disk usage. This process may take a moment ..."
  puts ""
  conn = clusters.first._connection
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')
  tasks = []
  clusters.each do |cluster|
    begin
      task = vvchs.VsanRebalanceCluster(
        :cluster => cluster)
      tasks << VIM::Task(conn, task._ref)
    end
  end
  progress(tasks)
end

def division x, y
  return y == 0 ? 0 : (x / y)
end

opts :cluster_query_object_identities do
  summary "Query the vSAN objects identity information"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource]
  opt :types, "The object types to be queried, usage: -t 'vm,iscsi,other,perf'.", :type => :string, :default => 'other'
  opt :skip_obj_info, "Skip fetching the object information.", :type => :boolean, :default => false
  opt :limit, "Only show the limited objects for each of object type. Default to show all", :type => :int
end

def cluster_query_object_identities cluster, opts = {}
  allTypes = {
    "vm" => ["vSAN Objects in VM", ["vmswap", "vdisk", "namespace", "vmen"]],
    "iscsi" => ["vSAN iSCSI Objects", ["iscsiTarget", "iscsiLun" ,"iscsiHome"]],
    "perf" => ["vSAN Performance Management Objects", ["statsdb"]],
    "other" => ['Unknown vSAN Objects', ['other']]
  }

  requiredTypes = allTypes.keys
  if not opts[:types].nil?
    requiredTypes = _verify_param(opts[:types].split(','),
      ['vm', 'iscsi', 'other', 'perf'], 'Invalid object types')

    if requiredTypes.empty?
      return
    end
  end

  limit = -1
  if not opts[:limit].nil?
    limit = opts[:limit].to_i
  end

  conn = cluster._connection
  vos = conn.vsanVcObjectSystem

  res = vos.VsanQueryObjectIdentities(
    :cluster => cluster,
    :includeObjIdentity => true,
    :includeHealth => true
  )
  if res.identities
    requiredTypes.each do |type|
      objTypes = allTypes[type]
      identities = res.identities.select{|r| objTypes[1].include?(r.type)}.map{|x| x.uuid}
      if not identities.empty?
        hasLimit = false
        if identities.length > limit and limit > 0
          identities = identities.slice(0, limit)
          hasLimit = true
        end
        puts "#{objTypes[0]} :"
        if opts[:skip_obj_info]
          objsInLine = 4 # Print 4 objects in each line
          slicedIden = identities.each_slice(objsInLine).to_a
          if hasLimit
            slicedIden[-1].push("...")
          end
          slicedIden.each{|x| puts "   #{x.join(", ")}"}
          puts ""
        else
          puts ""
          $shell.fs.marks['rvc_vsan_cluster'] = [cluster]
          cmd = "vsan.object_info ~rvc_vsan_cluster %s" % identities.join(" ")
          $shell.eval_command(cmd)
        end
      end
    end
  end
end

opts :health_summary do
  summary "Perform a basic health check"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem], :multi => true
  opt :create_vm_test, "Perform CreateVM test", :type => :boolean
end

def health_summary cluster_or_hosts, opts = {}
  if opts[:bypass_vc] && !opts[:password]
    err "Need to speficy either both --password and --bypass-vc or neither"
  end
  if !opts[:bypass_vc] && !cluster_or_hosts[0].is_a?(VIM::ClusterComputeResource)
    err "If --bypass-vc not used, must pass a cluster"
  end
  opts[:use_vc] = (opts[:bypass_vc] != true)
  times = []
  times << [Time.now, 'start']
  conn = cluster_or_hosts.first._connection
  pc = conn.propertyCollector
  model = VsanModel.new(
    cluster_or_hosts,
    ['vm'],
    :allow_multiple_clusters => false
  )
  hosts = model.basic['connected_hosts']
  hosts_props = model.basic['hosts_props']

  # XXX: Find vmknics instead?
  hostips = hosts.map{|x| hosts_props[x]['name']}
  allHostips = model.basic['hosts'].map{|x| hosts_props[x]['name']}
  allGroups = nil
  clusterStatus = nil

  if opts[:use_vc]
    hsConn = conn.vsanHealth

    vvchs = VIM::VimClusterVsanVcClusterHealthSystem(hsConn, 'vsan-cluster-health-system')

    cluster = cluster_or_hosts.first
    times << [Time.now, 'initial connect']
    res = vvchs.VsanQueryVcClusterHealthSummary(
      :cluster => cluster,
      :includeObjUuids => true,
      #:includeDataProtectionHealth => true
    )
    puts "Overall health: #{res.overallHealth} (#{res.overallHealthDescription})"
    allGroups = res.groups

    # Bug fix: 1477260
    # When 60u1 cluster only contains 60GA hosts, the default cluster status is disabled
    # so that the test result is empty
    if allGroups.empty?
      puts "No health check result. Please contact VMware Support."
      return
    end

    clusterStatus = res.clusterStatus
    disks = res.physicalDisksHealth
    clusterVersions = res.clusterVersions
    clomdLiveness = res.clomdLiveness
    net = res.networkHealth
    advcfg = res.advCfgSync
    obj = res.objectHealth
    limit = res.limitHealth
    times << [Time.now, 'cluster-health']
  else
    # host = hosts.find do |h|
      # enabled, = hosts_props[h]['configManager.vsanSystem'].collect 'config.enabled'
      # enabled
    # end
    # if !host
      # err "No host has vSAN enabled. Need at least one host that has vSAN enabled"
    # end
    # hostname = hosts_props[host]['name']
    # puts "Using host #{hostname}"
#
    # #pp host.name
    # hostConn = VIM.connect(:host => hostname, :user => 'root', :password => opts[:password],
                           # :insecure => true)
    # hostConn.debug = false
    # #pp hostips
    # hostDc = hostConn.serviceContent.rootFolder.childEntity.first
    # hostHost = hostDc.hostFolder.childEntity[0].host[0]
    # vchs = hostHost.vsanClusterHealthSystem
    # vhs = hostHost.vsanHealthSystem
    # vis = hostHost.configManager.vsanInternalSystem
    # times << [Time.now, 'initial connect']
    # clusterVersions = vchs.VsanQueryClusterHealthSystemVersions(
      # :hosts => allHostips, :esxRootPassword => opts[:password]
    # )
    # clomdLiveness = vchs.VsanCheckClusterClomdLiveness(
      # :hosts => allHostips, :esxRootPassword => opts[:password]
    # )
    # times << [Time.now, 'system-versions']
    # net = vchs.VsanQueryVerifyClusterNetworkSettings(
      # :hosts => allHostips, :esxRootPassword => opts[:password]
    # )
    # #pp net
    # times << [Time.now, 'network']
    # limit = vchs.VsanQueryClusterCheckLimits(
      # :hosts => hostips, :esxRootPassword => opts[:password]
    # )
    # times << [Time.now, 'resources/limits']
    # advcfg = vchs.VsanQueryClusterAdvCfgSync(
      # :hosts => hostips, :esxRootPassword => opts[:password]
    # )
    # times << [Time.now, 'advcfg']
    # obj = vhs.VsanHostQueryObjectHealthSummary(
      # :includeObjUuids => false
    # )
    # disks = nil
    # times << [Time.now, 'obj-health']
  end

  def hostUpdateRequired(clusterStatus)
    clusterStatus.trackedHostsStatus.each do |result|
      result.issues.each do |issue|
        return true if issue.include? "not updated"
      end
    end
    return false
  end

  if hostUpdateRequired(clusterStatus)
    puts "Warning: you need to update the all the host in this cluster"
    puts "         to perform a full set of vSAN health check."
  else
    noHF = limit.whatifHostFailures.find{|x| x.numFailures == 0}
    oneHF = limit.whatifHostFailures.find{|x| x.numFailures == 1}

    # XXX: ensure they are all on the same cluster UUID

    warnings = 0
    if net.hostsDisconnected.length > 0 || net.hostsCommFailure.length > 0
      puts "Warning: Not all hosts are connected/responding and hence visible"
      puts "         to this tool. Object health, resources, limits, etc. will"
      puts "         be based on incomplete data about the cluster."
      warnings += 1
    end
    if net.issueFound
      puts "Warning: A network/cluster issue was detected. This frequently impacts"
      puts "         object health directly. However in addition, this means this"
      puts "         tool doesn't have visibility of the entire cluster and several"
      puts "         checks will only consider a subset of hosts. Object health, "
      puts "         resources, limits, etc. will be based on incomplete data about "
      puts "         the cluster."
      warnings += 1
    end
  end

  if allGroups
    morTable = Hash[hosts_props.map{|host, props| [host._ref, props['name']]}]
    t = Terminal::Table.new()
    t << ['Health check', 'Result']
    anyFailed = false
    allGroups.each_with_index do |group, i|
      t.add_separator
      t << [group.groupName, mapHealthCode(group.groupHealth)]
      group.groupTests ||= []
      group.groupTests.each do |test|
        t << ["  #{test.testName}", mapHealthCode(test.testHealth)]
        if test.testHealth != "green"
          anyFailed = true
        end
      end
    end
    puts t

    if anyFailed
      puts ""
      puts "Details about any failed test below ..."
    end

    allGroups.each do |group|
      group.groupTests ||= []
      group.groupTests.each do |test|
        if test.testHealth == "green"
          next
        end
        if !test.testDetails
          next
        end
        if test.testDetails.length == 0
          next
        end
        puts "#{group.groupName} - #{test.testName}: #{test.testHealth}"
        test.testDetails.each do |details|
          displayGenericHealthDetails(details, :indent => 2,
                                      :replaceHealthIconInTable => false,
                                      :printTabelLabel => false,
                                      :conn => conn,
                                      :morTable => morTable)
        end
        puts ""
      end
    end
  end
  times << [Time.now, 'table-render']

  if opts[:create_vm_test]
    puts ""
    puts "Performing pro-active VM creation test ..."
    if opts[:use_vc]
      res = vvchs.VsanQueryVcClusterCreateVmHealthTest(
        :cluster => cluster,
        :timeout => 180
      )
    else
      res = vchs.VsanQueryClusterCreateVmHealthTest(
        :hosts => hostips, :esxRootPassword => opts[:password],
        :timeout => 180
      )
    end
    res = res.hostResults
    times << [Time.now, 'create-vm']
    issueFound = res.any?{|x| x.state != "success"}
    if !issueFound && 1 == 2
      puts "Success"
    else
      t = Terminal::Table.new()
      t << ['Check', 'Result']
      t.add_separator
      res.sort_by{|h| h.hostname}.each do |h|
        if h.state == 'success'
          error = 'Success'
        else
          error = []
          error << "#{h.fault.fault.class.wsdl_name}: #{h.fault.localizedMessage}"
          h.fault.fault.faultMessage.each do |msg|
            error << "  #{msg.key}: #{msg.message}"
          end
          error = error.map{|x| x.rstrip}.join("\n")
        end
        t << [h.hostname, error]
      end
      puts t
    end
    times << [Time.now, 'create-vm-table']
  end


  pp (times.length.times.to_a - [0]).map{|i| [times[i][0] - times[i - 1][0], times[i][1]]}
end


opts :cluster_debug_multicast do
  summary "Debug multicast"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource]
  opt :duration, "Duration to watch for packets. 1 minute is recommend", :type => :int, :default => 1 * 60
end

def cluster_debug_multicast cluster, opts
  cluster_or_hosts = [cluster]
  puts "#{Time.now}: Gathering information about hosts and vSAN"
  conn = cluster_or_hosts.first._connection
  pc = conn.propertyCollector
  model = VsanModel.new(
    cluster_or_hosts,
    [],
    :allow_multiple_clusters => false
  )
  cluster = cluster_or_hosts.first
  if cluster_or_hosts.is_a?(VIM::ClusterComputeResource) && !opts[:cluster_uuid]
    prop = 'configurationEx.vsanConfigInfo.defaultConfig.uuid'
    opts[:cluster_uuid], = cluster.collect(prop)
  end
  hosts = model.basic['connected_hosts']
  hosts_props = model.basic['hosts_props']

  hsConn = conn.vsanHealth
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(hsConn, 'vsan-cluster-health-system')

  hosts_vsanprops = pc.collectMultiple(
    hosts.map{|h| hosts_props[h]['configManager.vsanSystem']},
    'config.clusterInfo',
    'config.networkInfo',
  )
  nodeUuidToHostMap = {}
  networkInfoMap = {}

  lock = Mutex.new
  allPackets = {}
  hostStarttime = {}
  startTime = Time.now.to_f

  chars = ('A'..'Z').to_a + ('1'..'9').to_a
  hostChars = {}
  hosts = hosts.sort_by{|host| hosts_props[host]['name']}

  host = hosts.first

  duration = opts[:duration]
  puts "#{Time.now}: Watching packets for #{duration} seconds"
  latestStarttime = []
  hostPackets = {}
  timestr = Time.now.strftime('%Y-%m-%d.%H-%M-%S')
  tmpdir = Dir.mktmpdir("rvc-multicast-tcpdump-#{timestr}")

  res = nil
  begin
    res = vvchs.VsanVcQueryClusterCaptureVsanPcap(
      :cluster => cluster,
      :duration => opts[:duration],
      :clusterUuid => opts[:cluster_uuid],
      :cmmdsMsgTypeFilter => ['MASTER_HEARTBEAT'],
      :includeIgmp => false,
      :includeRawPcap => true
    )
  rescue Exception => ex
    pp ex
    raise
  end

  puts "#{Time.now}: Got observed packets from all hosts, analysing"

  puts ""
  if !res.issues || res.issues.length == 0
    puts "Automated system couldn't derive any issues."
    puts "Either no problem exists or manual inspection is required."
  else
    puts "To function properly vSAN requires all hosts in the cluster"
    puts "have multicast connectivity to each other. This tool groups"
    puts "hosts based on multicast connectivity, and so the correct"
    puts "state is a single group. In this environment however, #{res.groups.length}"
    puts "groups were detected. Use the following information to work"
    puts "with the network admin further troubleshoot the physical"
    puts "network connecting the ESX hosts to each other."
    puts ""
    # XXX: Also list non-issues
    puts "Identified issues:"
    res.issues.each do |issue|
      puts "  Issue: #{issue}"
    end
    puts ""
    puts "Identified connecitity groups:"
    t = Terminal::Table.new()
    t << ['Master', 'Members']
    res.groups.each do |group|
      t.add_separator
      t << [group.master, group.members.join("\n")]
    end
    puts t
  end

  puts ""
  puts "To further help the network admin, the following is a list of"
  puts "packets with source and destination IPs. As all these packets"
  puts "are multicast, they should have been received by all hosts in"
  puts "the cluster. To show which hosts actually saw the packets, each"
  puts "host is represented by a character (A-Z). If the character is "
  puts "listed in front of the packet, the host received the packet. If"
  puts "the space is left empty, the host didn't receive the packet."
  puts ""
  metapackets = res.pkts
  hosts.each_with_index do |host, i|
    hostChars[hosts_props[host]['name']] = chars[i]
    puts "#{chars[i]} = Host #{hosts_props[host]['name']}"
  end

  metapackets.sort_by{|x| x['timestamp']}.each do |info|
    info = JSON.load(info)
    hosts = info['seenBy']
    hostRecvStr = ""
    hostChars.each do |host, char|
      if hosts.member?(host)
        hostRecvStr += char
      else
        hostRecvStr += " "
      end
    end

    pkt = info
#    pkt['normTsStr'] = "%.2f" % pkt['normTs']
    if pkt['pktType'] == 'cmmds'
      # if opts[:no_agenthb] && pkt['msgType'] == 'AGENT_HEARTBEAT'
        # next
      # end

      srcHost = nodeUuidToHostMap[pkt['srcUuid']]
      if srcHost
        srcHost = hosts_props[srcHost]['name']
      else
        srcHost = pkt['srcUuid']
      end
      str = "%.2f: %26s (#%08d) from:%s(%s) to:%s" % [
        pkt['timestamp'],
        pkt['msgType'],
        pkt['cmmdsMcastSeq'],
        pkt['srcIp'], hostChars[srcHost],
        pkt['dstIp'],
      ]
    elsif pkt['pktType'] == 'igmp'
      igmp = pkt
      str = "#{igmp['normTsStr']}: #{igmp['msgType']} - GA: #{igmp['igmpGA']}"
    end

    puts "[#{hostRecvStr}] #{str}"

  end

end

opts :health_check_interval_configure do
  summary "Configure the health check interval (in minutes) for the cluster; default to 60 minutes."
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
  opt :interval, "Basic Health Check Interval, set to 0 for disable", :type => :int, :default => 60
end

def health_check_interval_configure clusters, opts = {}
  conn = clusters.first._connection
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')

  clusters.each do |cluster|
    begin
      if (opts[:interval] > 0 and opts[:interval] < 15) or opts[:interval] > 1440
        raise "only allow interval between 15 mins and 1 day"
      end
      vvchs.VsanHealthSetVsanClusterHealthCheckInterval(
        :cluster => cluster,
        :vsanClusterHealthCheckInterval => opts[:interval])
      if opts[:interval] == 0
        puts "Disabled the periodical health check for #{cluster.name}"
      else
        puts "Successfully set the health check interval for #{cluster.name} to #{opts[:interval]} minutes!"
      end
    rescue Exception => ex
      puts "Failed to set health check interval for cluster #{cluster.name}: #{ex.message}"
    end
  end
end

opts :health_check_interval_status do
  summary "Get the current health check interval status"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
end

def health_check_interval_status clusters, opts = {}
  conn = clusters.first._connection
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')

  t = Terminal::Table.new()
  t << ['Cluster', 'Health Check Interval']
  t.add_separator
  clusters.each do |cluster|
    begin
      name = cluster.name
      interval =
        vvchs.VsanHealthQueryVsanClusterHealthCheckInterval(:cluster => cluster)
      if interval == 0
        t << [name, "Disabled"]
      else
        t << [name, "#{interval} mins"]
      end
      puts t
    rescue Exception => ex
      puts "Failed to set health check interval for cluster #{cluster.name}: #{ex.message}"
    end
  end
end

def _verify_param sublist,fulllist, errMsg = "Invalid health check id"
  if sublist.empty?
    fulllist.each_with_index do |item, index|
      puts "#{index}: #{item.groupName} - #{item.testName}"
    end
    puts "Choose the check number: ([0,1,2...])"
    input = $stdin.gets.chomp()
    input.split(',').each do |item|
      if item.to_i.to_s != item or fulllist[item.to_i].nil?
        puts "Invalid input: #{item}"
        return []
      end
    end
    return input.split(',')
  else
    sublist.each do |item|
      if not fulllist.include?(item)
        puts "#{errMsg}: #{item}"
        return []
      end
    end
    return sublist
  end
end

def _get_all_checks_hash allchecklist
  allchecks = {}
  sortedchecks = allchecklist.sort_by{ |a| [a.groupName, a.testName]}
  sortedchecks.each do | test_info |
    allchecks[test_info.groupId + '.' + test_info.testId] = test_info
  end
  return allchecks
end

opts :silent_health_check_configure do
  summary "Configure silent health check list for the given cluster"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource]#, :multi => true
  opt :add_checks, "Add checks to silent list, usage: -a [Health Check Id].", :type => :string
  opt :remove_checks, "Remove checks from silent list, usage: -r [Health Check Id]. To restore the silent check list, using '-r all'", :type => :string
  opt :interactive_add, "Use interactive mode to add checks to the silent list", :type => :boolean
  opt :interactive_remove, "Use interactive mode to remove checks from the silent list", :type => :boolean
end

def silent_health_check_configure cluster, opts = {}
  if opts[:add_checks].nil? and opts[:remove_checks].nil? and !opts[:interactive_add] and !opts[:interactive_remove]
    puts "Nothing changed! Please give at least one of the arguments. Use '--help' to see the help message"
    return
  end

  conn = cluster._connection
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')
  allchecklist = vvchs.VsanQueryAllSupportedHealthChecks()
  allchecks = _get_all_checks_hash(allchecklist)
  check_ids = allchecks.keys
  pure_check_ids = []
  check_ids.each do | checkid |
    groupid, testid = checkid.split('.')
    pure_check_ids.push(testid)
    if not pure_check_ids.include?(groupid)
       pure_check_ids.push(groupid)
    end
  end
  check_infos = allchecks.values

  addlist = []
  rmlist = []
  if not opts[:add_checks].nil?
    addlist = _verify_param(opts[:add_checks].split(','), pure_check_ids)
  end
  if opts[:interactive_add]
    addids = _verify_param([],check_infos)
    addids.each do | id |
      addlist.push(check_ids[id.strip.to_i].split('.')[-1])
    end
  end
  silent_check_ids = vvchs.VsanHealthGetVsanClusterSilentChecks(:cluster => cluster)
  if not opts[:remove_checks].nil?
    rmlist = _verify_param(opts[:remove_checks].split(','), pure_check_ids.push('all'))
  end
  if opts[:interactive_remove]
    if silent_check_ids.empty?
      puts "Silent health check list is empty!"
    else
      silent_check_infos = []
      silent_check_ids.each do | id |
        check_ids.each do | checkid |
          if checkid.split('.')[-1] == id
            allchecks[checkid].groupName = ''
            silent_check_infos.push(allchecks[checkid])
            break
          end
        end
      end
      rmids = _verify_param([], silent_check_infos)
      rmids.each do | id |
        rmlist.push(silent_check_ids[id.strip.to_i])
      end
    end
  end
  if rmlist.empty? and addlist.empty?
    puts "Please input again"
    return
  end

  begin
    res = vvchs.VsanHealthSetVsanClusterSilentChecks(
       :cluster => cluster,
       :addSilentChecks => addlist.uniq,
       :removeSilentChecks => rmlist
    )
    if not addlist.empty? or not rmlist.empty?
      if rmlist == ['all']
        puts "Successfully restore silent check list for #{cluster.name}"
      else
        puts "Successfully update silent health check list for #{cluster.name}"
      end
    end
  rescue Exception => ex
    puts "Failed to set silent health check list for cluster #{cluster.name}: #{ex.message}"
  end
end

opts :silent_health_check_status do
  summary "Get the current silent health check list for the given cluster"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
end

def silent_health_check_status clusters, opts = {}
  conn = clusters.first._connection
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')

  clusters.each do |cluster|
    puts "Silent Status of Cluster #{cluster.name}:"
    t = Terminal::Table.new()
    t << ['Health Check', 'Health Check Id', 'Silent Status']
    begin
      clustername = cluster.name
      allchecklist = vvchs.VsanQueryAllSupportedHealthChecks()
      allchecks = _get_all_checks_hash(allchecklist)
      silent_check_ids = vvchs.VsanHealthGetVsanClusterSilentChecks(:cluster => cluster)
      count = 0
      groupName = ""
      allchecks.keys.each do | id |
        if allchecks[id].groupName != groupName
          t.add_separator
          t << [allchecks[id].groupName, "", ""]
          groupName = allchecks[id].groupName
        end
        groupid, testid = id.split('.')
        if silent_check_ids.include?(groupid)
          t << ["  #{allchecks[id].testName}", testid, 'Silent']
        else
          if silent_check_ids.include?(testid)
            t << ["  #{allchecks[id].testName}", testid, 'Silent']
          else
            t << ["  #{allchecks[id].testName}", testid, 'Normal']
          end
        end
      end
      puts t
    rescue Exception => ex
      puts "Failed to get silent health check list for cluster #{cluster.name}: #{ex.message}"
    end
  end
end
