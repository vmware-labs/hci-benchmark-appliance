require 'rbvmomi'
require 'rvc/vim'
require 'rbvmomi/pbm'

def watch_task conn, task
  if conn.vsan_standalone_mode
    one_progress task
    return
  end
  taskId = task._ref
  em = conn.serviceContent.eventManager
  task = VIM::Task(conn, taskId)
  chainId = task.info.eventChainId
  seenKeys = []
  prevProgress = 0
  prevDescr = ''
  while true
    taskInfo = task.info
    events = em.QueryEvents(:filter => {:eventChainId => chainId})

    events.each do |event|
      if seenKeys.member?(event.key)
        next
      end
      puts event.fullFormattedMessage
      seenKeys << event.key
    end

    if !['running', 'queued'].member?(taskInfo.state)
      puts "Task result: #{taskInfo.state}"
      break
    else
      if taskInfo.progress && taskInfo.progress > prevProgress
        puts "New progress: #{taskInfo.progress}%"
        prevProgress = taskInfo.progress
      end
      if taskInfo.description
        msg = taskInfo.description.message
        if msg != prevDescr
          puts "New status: #{msg}"
          prevDescr = msg
        end
      end
    end

    sleep 2
  end
end

def with_gnuplot persist
  if $rvc_gnuplot
    yield $rvc_gnuplot
  else
    cmd = Gnuplot.gnuplot(persist) or err 'gnuplot not found'
    $rvc_gnuplot = IO::popen(cmd, "w")
    begin
      yield $rvc_gnuplot
    ensure
      gp = $rvc_gnuplot
      $rvc_gnuplot = nil
      gp.close
    end
  end
end


def require_gnuplot
  begin
    require 'gnuplot'
  rescue LoadError
    no_spec_reset = false
    begin
      Gem::Specification.reset
    rescue NoMethodError
      no_spec_reset = true
    end
    begin
      require 'gnuplot'
    rescue LoadError
      if no_spec_reset
        puts "WARNING: Gem::Specification.reset method is not supported."
        puts "WARNING: This version of Ruby is lower than 1.9.3"
      end
      err "The gnuplot gem is not installed"
    end
  end
end

TIMEFMT = '%Y-%m-%dT%H:%M:%SZ'

opts :query_timerange do
  summary "Queries a time range"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource], :multi => true
end

def query_timerange clusters, opts = {}
  require_gnuplot
  require 'csv'

  conn = clusters.first._connection
  pc = conn.serviceContent.propertyCollector
  vpm = conn.vsanVcPerformanceManager
  # XXX: Don't hardcode the metric we fetch
  metricLabel = 'throughput'
  clusters.each do |cluster|
    # pp vpm.VsanPerfQueryStatsObjectInformation(:cluster => cluster)
    now = Time.now
    hosts = cluster.host
    hosts_props = pc.collectMultiple(hosts, 'name', 'configManager.vsanSystem')
    refToHost = {}
    # XXX: Also support querying entities other than hosts/DomClients
    specs = hosts.map do |host|
      vsanSys = hosts_props[host]['configManager.vsanSystem']
      hostUuid = vsanSys.collect('config.clusterInfo.nodeUuid').first
      spec = VIM::VsanPerfQuerySpec(
        :entityRefId => 'host:%s' % hostUuid,
        :group => 'DomClient',
        :startTime => now - 60 * 15, # in sec
        :endTime => now,
      )
      refToHost[spec.entityRefId] = host
      spec
    end
    t1 = Time.now
    allStats = vpm.VsanPerfQueryPerf(
      :querySpecs => specs,
      :cluster => cluster
    )
    t2 = Time.now
    pp (t2 - t1)
    data = allStats.map do |res|
      host = refToHost[res.entityRefId]
      if res.sampleInfo == ""
        puts "No data for entity %s" % res.entityRefId
        next
      end
      iops = res.value.find{|x| x.metricId.label == metricLabel}
      times = res.sampleInfo.parse_csv
      times = times.map{|x| x.split('.').first}.map{|x| x.gsub(' ', 'T')}
      values = iops.values.parse_csv.map(&:to_f)
      pp iops.values

      Gnuplot::DataSet.new([times, values]) do |ds|
#        ds.notitle
        ds.with = "lines"
        ds.using = '1:2'
        ds.title = hosts_props[host]['name']
      end
    end.compact
    with_gnuplot(true) do |gp|
      plot = Gnuplot::Plot.new(gp) do |plot|
        plot.title metricLabel

        plot.ylabel metricLabel
        plot.xlabel "Time"
        plot.terminal 'dumb'

        plot.set 'xdata', 'time'
        plot.set 'format', "x '%H:%M'"
        plot.set 'timefmt', TIMEFMT.inspect

        plot.data = data.compact
      end
      gp.puts
    end
  end
end

def _getProfileSpec(opts)
  if opts[:policy] && opts[:policy_str]
    err "Need to specify only one of --policy or --policy-str"
  end

  profile = nil
  if opts[:policy]
    profile = VIM::VirtualMachineDefinedProfileSpec(
      :profileId => opts[:policy].profileId.uniqueId
    )
  end
  if opts[:policy_str]
    profile = VIM::VirtualMachineDefinedProfileSpec(
      :profileId => '',
      :profileData => {
        :extensionKey => 'com.vmware.vim.sps',
        :objectData => opts[:policy_str]
      }
    )
  end
  return profile
end

opts :stats_object_setpolicy do
  summary "Set the policy of the vSAN Stats object"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource]
  opt :policy_str, "Policy, expressed as string, e.g. vSAN format", :type => :string
  opt :policy, "Policy, reference to SPBM profile", :lookup => RbVmomi::PBM::PbmCapabilityProfile
end

def stats_object_setpolicy cluster, opts = {}
  profile = _getProfileSpec(opts)
  if !opts[:policy] && !opts[:policy_str]
    err "Need to specify either --policy or --policy-str"
  end

  conn = cluster._connection
  pc = conn.serviceContent.propertyCollector
  vpm = conn.vsanVcPerformanceManager

  pp profile
  pp vpm.VsanPerfSetStatsObjectPolicy(
    :cluster => cluster,
    :profile => profile
  )
end

opts :stats_object_info do
  summary "Display information about the vSAN Stats object"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource]
end

def stats_object_info cluster, opts = {}
  conn = cluster._connection
  pc = conn.serviceContent.propertyCollector
  vpm = conn.vsanVcPerformanceManager

  info = nil
  begin
    info = vpm.VsanPerfQueryStatsObjectInformation(:cluster => cluster)
  rescue VIM::FileNotFound
    err "vSAN Stats object is not found."
  end
  puts "Directory Name: %s" % (info.directoryName || "(Not found)")
  profileName = 'None'
  notes = ''
  if info.spbmProfileUuid
    _catch_spbm_resets(conn) do
      pm = conn.pbm.serviceContent.profileManager
      begin
        profile = pm.PbmRetrieveContent(:profileIds => [{
          :uniqueId => info.spbmProfileUuid
        }])
        profile = profile.first
        profileName = profile.name
        notes = ''
        if info.spbmProfileGenerationId.to_i != profile.generationId
          notes = ' (Out of date)'
        end
      rescue VIM::InvalidArgument
        profileName = info.spbmProfileUuid
        notes = ' (Profile not found)'
      rescue RbVmomi::PBM::SecurityError
        profileName = info.spbmProfileUuid
        notes = ' (No permission to retrieve profile)'
      rescue RbVmomi::Fault
        profileName = info.spbmProfileUuid
        notes = ' (Profile not found)'
      end
    end
  end
  puts "vSAN Object UUID: %s" % (info.vsanObjectUuid || "(Not found)")
  puts "SPBM Profile: %s%s" % [profileName, notes]
  policyStr = info.policyAttributes.map{|k,v| '%s: %s' % [k,v]}.join(', ')
  puts "vSAN Policy: %s" % policyStr
  if info.vsanObjectUuid
    puts "vSAN Object Health: %s" % [info.vsanHealth || 'unknown']
    puts ""
    $shell.fs.marks['rvc_vsan_perf_cluster'] = [cluster]
    cmd = "vsan.object_info ~rvc_vsan_perf_cluster %s" % info.vsanObjectUuid
    $shell.eval_command(cmd)
  end
end

opts :stats_object_create do
  summary "Create the stats object"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource]
  opt :policy_str, "Policy, expressed as string, e.g. vSAN format", :type => :string
  opt :policy, "Policy, reference to SPBM profile", :lookup => RbVmomi::PBM::PbmCapabilityProfile
end

def stats_object_create cluster, opts = {}
  profile = _getProfileSpec(opts)

  conn = cluster._connection
  pc = conn.serviceContent.propertyCollector
  vpm = conn.vsanVcPerformanceManager
  info = nil
  begin
    info = vpm.VsanPerfQueryStatsObjectInformation(:cluster => cluster)
  rescue VIM::FileNotFound
    info = nil
  end
  if info && info.vsanObjectUuid
    err "Existing stats object found, check vsan.perf.stats_object_info"
  end
  if profile
    pp profile
  end
  puts "Creating vSAN Stats DB object, which will enable vSAN Performance Service ..."
  begin
    task = vpm.VsanPerfCreateStatsObjectTask(
       :cluster => cluster,
       :profile => profile
    )
    watch_task(conn, task)
  rescue VIM::VsanFault => ex
    puts "Failed to enable vSAN Performance Service. #{cluster.name}: #{ex.message}"
    ex.fault.faultMessage.each do |msg|
      puts "   #{msg.key}: #{msg.message}"
    end
  end
end


opts :stats_object_delete do
  summary "Delete the stats object"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource]
end

def stats_object_delete cluster, opts = {}
  conn = cluster._connection
  pc = conn.serviceContent.propertyCollector
  vpm = conn.vsanVcPerformanceManager

  info = vpm.VsanPerfQueryStatsObjectInformation(:cluster => cluster)
  if !info.vsanObjectUuid
    err "Didn't find any existing stats object"
  end

  # XXX: Need to ask user for permission
  puts "Deleting vSAN Stats DB object, which will stop vSAN Performance Service ..."
  begin
    task = vpm.VsanPerfDeleteStatsObjectTask(:cluster => cluster)
    watch_task(conn, task)
  rescue VIM::VsanFault => ex
    puts "Failed to delete vSAN Stats DB object. #{cluster.name}: #{ex.message}"
    ex.fault.faultMessage.each do |msg|
      puts "   #{msg.key}: #{msg.message}"
    end
  end
end


opts :cluster_info do
  summary "Per-host information about vSAN perf service"
  arg :cluster, nil, :lookup => [VIM::ClusterComputeResource]
end

def cluster_info cluster, opts = {}
  conn = cluster._connection
  pc = conn.serviceContent.propertyCollector
  vpm = conn.vsanVcPerformanceManager

  nodes = vpm.VsanPerfQueryNodeInformation(:cluster => cluster)
  t = Terminal::Table.new()
  t << ['Hostname', 'Role', 'Issues']
  t.add_separator
  nodes.each do |node|
    role = []
    if node.isCmmdsMaster
      role << "CMMDS Master"
    end
    if node.isStatsMaster
      role << "Stats Master"
    end
    if role.length == 0
      role << "Agent"
    end
    errors = []
    if node.error
      error = []
      fault = node.error
      error << "#{fault.fault.class.wsdl_name}: #{fault.localizedMessage}"
      fault.fault.faultMessage.each do |msg|
        error << "  #{msg.key}: #{msg.message}"
      end
      errors << error.map{|x| x.rstrip}.join("\n")
    end
    if node.masterInfo
      # XXX: Translation to health issues should happen in health code
      (node.masterInfo.renamedStatsDirectories || []).each do |dir|
        errors << "Found renamed Stats DB dir: #{dir}"
      end
      freePct = node.masterInfo.statsDirectoryPercentFree
      if freePct <= 5
        errors << "Error: Only %d%% free space in Stats DB object" % freePct
      elsif freePct < 20
        errors << "Warning: Only %d%% free space in Stats DB object" % freePct
      end
      interval = node.masterInfo.statsIntervalSec
      lastCollect = node.masterInfo.secSinceLastStatsCollect
      lastWrite = node.masterInfo.secSinceLastStatsWrite
      if !lastCollect || lastCollect > interval * 3
        errors << "Error: No successful stats collection in 2 intervals"
      elsif !lastWrite || lastWrite > interval * 3
        errors << "Error: No successful stats persistence in 2 intervals"
      end
    end
    if errors.length == 0
      errors << "None"
    end
    t << [
      node.hostname,
      role.join(", "),
      errors.join("\n")
    ]
  end
  puts t
end



opts :resync_dashboard do
  summary "Resyncing dashboard"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :refresh_rate, "Refresh interval (in sec). Default is no refresh", :type => :int
end

def resync_dashboard cluster_or_host, opts
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  _run_with_rev(conn, "dev") do
    model = VsanModel.new([cluster_or_host])
    connected_hosts = model.basic['connected_hosts']
    hosts_props = model.basic['hosts_props']
    host = connected_hosts.first
    hostname = hosts_props[host]['name']
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']

    vsanSysList = Hash[hosts_props.map do |host, props|
      [props['name'], props['configManager.vsanSystem']]
    end]
    clusterInfos = pc.collectMultiple(vsanSysList.values,
                                      'config.clusterInfo')
    hostUuidMap = Hash[vsanSysList.map do |hostname, sys|
      [clusterInfos[sys]['config.clusterInfo'].nodeUuid, hostname]
    end]

    entries = nil

    vmsProps = {}

    vsanNs = $shell.cmds[:vsan].slate
    iter = 0
    while (iter == 0) || opts[:refresh_rate]
      puts "#{Time.now}: Querying all objects in the system from #{hostname} ..."

      result = vsanIntSys.query_syncing_vsan_objects({})
      if !result
        err "Server failed to gather syncing objects"
      end
      objects = result['dom_objects']

      objects = objects.map do |uuid, objInfo|
        obj = objInfo['config']
        comps = vsanNs._components_in_dom_config(obj['content'])
        bytesToSyncTotal = 0
        recoveryETATotal = 0
        comps = comps.select do |comp|
          state = comp['attributes']['componentState']
          bytesToSync = comp['attributes']['bytesToSync'] || 0
          recoveryETA = comp['attributes']['recoveryETA'] || 0
          resync = [10, 6].member?(state) && bytesToSync != 0
          if resync
            bytesToSyncTotal += bytesToSync
            recoveryETATotal = [recoveryETA, recoveryETATotal].max
          end
          resync
        end
        obj['bytesToSync'] = bytesToSyncTotal
        obj['recoveryETA'] = recoveryETATotal
        if comps.length > 0
          obj
        end
      end.compact
      obj_uuids = objects.map{|x| x['uuid']}
      objects = Hash[objects.map{|x| [x['uuid'], x]}]

      vmToObjMap = {}
      if obj_uuids.length > 0
        puts "#{Time.now}: Query object identities ..."
        vos = conn.vsanVcObjectSystem
        objIdents = vos.VsanQueryObjectIdentities(
          :cluster => cluster_or_host,
          :objUuids => obj_uuids,
          :includeObjIdentity => true,
        )
        # XXX: Handle case where some objects belong to multiple VMs
        vmsToLookup = []
        objIdents.identities.each do |objIdent|
          vm = 'Unassociated'
          if objIdent.vm
            vm = VIM::VirtualMachine(conn, objIdent.vm._ref)
            if !vmsProps[vm]
              vmsToLookup << vm
            end
          end
          vmToObjMap[vm] ||= {}
          vmToObjMap[vm][objIdent.uuid] = objIdent.description
        end
        if vmsToLookup.length > 0
          puts "#{Time.now}: Query VMs ..."
          vmsProps.merge!(pc.collectMultiple(vmsToLookup, 'name'))
        end
      end

      puts "#{Time.now}: Got all the info, computing table ..."
      t = Terminal::Table.new()
      t << [
        'VM/Object',
        'Syncing objects',
        'Bytes to sync',
        #'ETA',
      ]
      t.add_separator
      bytesToSyncGrandTotal = 0
      objGrandTotal = 0
      vmToObjMap.sort_by do |vm, _|
        vm.is_a?(VIM::VirtualMachine) ? 0 : 1
      end.each do |vm, vm_obj_uuids|
        if vm.is_a?(VIM::VirtualMachine)
          vmProps = vmsProps[vm]
          vmName = vmProps['name']
        else
          vmName = vm
        end
        objs = vm_obj_uuids.keys.map{|x| objects[x]}
        bytesToSyncTotal = objs.map{|obj| obj['bytesToSync']}.sum
        recoveryETATotal = objs.map{|obj| obj['recoveryETA']}.max
        t << [
          vmName,
          objs.length,
          "", #"%.2f GB" % (bytesToSyncTotal.to_f / 1024**3),
          #"%.2f min" % (recoveryETATotal.to_f / 60),
        ]
        objs.each do |obj|
          t << [
            "   %s" % (vm_obj_uuids[obj['uuid']] || obj['uuid']),
            '',
            "%.2f GB" % (obj['bytesToSync'].to_f / 1024**3),
            #"%.2f min" % (obj['recoveryETA'].to_f / 60),
          ]
        end
        bytesToSyncGrandTotal += bytesToSyncTotal
        objGrandTotal += objs.length
      end
      t.add_separator
      t << [
        'Total',
        objGrandTotal,
        "%.2f GB" % (bytesToSyncGrandTotal.to_f / 1024**3),
        #"%.2f min" % (recoveryETATotal.to_f / 60),
      ]
      puts t
      iter += 1

      if opts[:refresh_rate]
        sleep opts[:refresh_rate]
      end
    end
  end
end


def _catch_spbm_resets(conn)
  begin
    yield
  rescue EOFError
    if conn
      conn.pbm = nil
    end
    err "Connection to SPBM timed out, try again"
  end
end
