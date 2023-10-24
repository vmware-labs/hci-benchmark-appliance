require 'fileutils'
require 'open-uri'

if !defined?(VIM)
  VIM = RbVmomi::VIM
end

class NullLogger
  def info x
    # Do nothing
  end

  def close
    # Do nothing
  end
end

class SimpleLogger < NullLogger
  def info x
    puts "#{Time.now}: #{x}"
  end
end

class FileLogger
  def initialize filename
    @fp = open(filename, 'a')
  end

  def info x
    @fp.puts "#{Time.now}: #{x}"
#    puts "FILE: #{Time.now}: #{x}"
    @fp.flush
  end

  def close
    @fp.close
  end
end


def _read_file fileName
  if File.exist?(fileName)
    return File.open(fileName, "r").read()
  end
  return nil
end

def _write_file fileName, content
  file = File.new(fileName, "w")
  file.write content
  file.close
end



def _ondisk_upgrade_checkcluster logger, conn, pc, hosts, opts = {}
  hosts_props = _ondisk_upgrade_get_hosts_props conn, pc, hosts
  op = opts[:downgrade_format] ? "Downgrade" : "Upgrade"

  out = {
    'hosts_props' => hosts_props,
  }
  disconnected_hosts = hosts_props.select do |k,v|
    v['runtime.connectionState'] != 'connected'
  end.keys
  if disconnected_hosts.length > 0
    out['issue'] = RbVmomi::VIM::VsanUpgradeSystemHostsDisconnectedIssue(
      :hosts => disconnected_hosts,
      :msg =>
        "The following hosts are not connected. #{op} can't proceed " +
        "unless all hosts are connected to VC. "
    )
    return out
  end

  error = false
  hosts_props.map do |host, props|
    Thread.new do
      begin
        vsanSys = props['configManager.vsanSystem']
        c1 = conn.spawn_additional_connection
        vsanSys  = vsanSys.dup_on_conn(c1)
        res = vsanSys.QueryHostStatus()
        hosts_props[host]['vsanCluster'] = res
      rescue Exception => ex
        puts "Failed to gather host status from #{props['name']}: #{ex.class}: #{ex.message}"
        error = true
      end
    end
  end.each{|t| t.join}
  if error
    out['issue'] = RbVmomi::VIM::VsanUpgradeSystemPreflightCheckIssue(
      :msg => "Failed to gather all host statuses. #{op} is being halted.",
    )
    return out
  end

  partitions = hosts_props.group_by{|h, p| p['vsanCluster'].memberUuid}
  partition_exists = (partitions.length > 1)
  if partition_exists
    out['issue'] = RbVmomi::VIM::VsanUpgradeSystemNetworkPartitionIssue(
      :msg => "Detected that the vSAN cluster is network partitioned, i.e. " +
         "not all hosts can communicate with each other over the vSAN " +
         "network. #{op} can't proceed until the network partition is " +
         "resolved.",
      :partitions => partitions.map do |uuid, hosts|
        RbVmomi::VIM::VsanUpgradeSystemNetworkPartitionInfo(
          :hosts => Hash[hosts].keys
        )
      end
    )
    return out
  end

  members = hosts_props.values.first['vsanCluster'].memberUuid
  nodeUuids = Hash[hosts_props.map{|k,v| [k, v['vsanCluster'].nodeUuid]}]
  missingHosts = []
  nodeUuids.each do |host, nodeUuid|
    if !members.member?(nodeUuid)
      missingHosts << host
    end
  end
  if missingHosts.length > 0
    out['issue'] = RbVmomi::VIM::VsanUpgradeSystemMissingHostsInClusterIssue(
      :msg => "Not all hosts in the VC cluster are participating in the " +
         "vSAN cluster. #{op} has been halted and can't proceed until " +
         "this issue is resolved.",
      :hosts => missingHosts,
    )
    return out
  end
  extraUuids = members - nodeUuids.values
  if extraUuids.length > 0
    out['issue'] = RbVmomi::VIM::VsanUpgradeSystemRogueHostsInClusterIssue(
      :msg => "Hosts that are not in given host list or VC cluster were detected to " +
         "participate in the vSAN cluster. #{op} has been halted and " +
         "can't proceed until this issue is resolved.",
      :uuids => extraUuids,
    )
    return out
  end

  incorrectVersion = hosts_props.select do |k, v|
    v['config.product'].version != "6.0.0"
  end.keys
  if incorrectVersion.length > 0
    out['issue'] = RbVmomi::VIM::VsanUpgradeSystemWrongEsxVersionIssue(
      :msg => "Detected hosts that aren't running 6.0. #{op} has been " +
         "halted. #{op} can't proceed unless all hosts are running ESX " +
         "6.0.",
      :hosts => incorrectVersion,
    )
    return out
  end

  autoClaimHosts = hosts_props.select do |k, v|
    v['vsan.autoClaimStorage']
  end.keys
  if autoClaimHosts.length > 0
    out['issue'] = RbVmomi::VIM::VsanUpgradeSystemAutoClaimEnabledOnHostsIssue(
      :msg => "Detected hosts that have vSAN disk auto-claim enabled. " +
         "#{op} has been halted. Disable auto-claim at the cluster " +
         "level. ",
      :hosts => autoClaimHosts,
    )
    return out
  end

  # Detect inaccessible objects, which block data evacuation during upgrade

  vsanIntSys = hosts_props.values.first['configManager.vsanInternalSystem']
  statuses = vsanIntSys.query_cmmds([{:type => 'CONFIG_STATUS'}])
  bad = statuses.select do |x|
    state = _assessAvailabilityByStatus(x['content']['state'])
    !state['DATA_AVAILABLE'] || !state['QUORUM']
  end
  if !bad.empty?
    inaccessible_objects = bad.map{|x| x['uuid']}
    out['issue'] = RbVmomi::VIM::VsanUpgradeSystemPreflightCheckIssue(
      :msg => "Detected inaccessible objects in vSAN. #{op} has been halted. " \
         "Please fix or remove them and try again. " \
         "Try \"vsan.purge_inaccessible_vswp_objects\" command which can " \
         "be useful to purge inaccessible vswp objects. " \
         "Following inaccessible objects were detected:\n" +
         inaccessible_objects.join("\n")
    )
    return out
  end

  # Detect unhealthy disks used by vSAN, which block data evacuation during vSAN upgrade.

  _run_with_rev(conn, "dev") do
    all_disks = vsanIntSys.QueryPhysicalVsanDisks(:props => [
      'uuid',
      'disk_health',
    ])

    if all_disks == "BAD"
      raise "Server failed to gather vSAN disk info"
    end
    begin
      all_disks = JSON.load(all_disks)
    rescue
      err "Server didn't provide vSAN disk info: #{all_disks}"
    end

    all_disks.each do |uuid, x|
      if x['disk_health'] && x['disk_health']['healthFlags']
        flags = x['disk_health']['healthFlags']
        health = []
        {
          4 => "FAILED",
          5 => "OFFLINE",
          6 => "DECOMMISSIONED",
        }.each do |k, v|
          if flags & (1 << k) != 0
            out['issue'] = RbVmomi::VIM::VsanUpgradeSystemPreflightCheckIssue(
              :msg => "Detected unhealthy disks used by vSAN. #{op} has been halted. " +
                "Please fix or remove them and try again. " +
                "Command vsan.disks_stats could help to check disk status."
            )
            return out
          end
        end
      end
    end
  end

  _run_with_rev(conn, "dev") do
    host = hosts_props.keys.first
    # XXX: We may want to make this call to all hosts to double check
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
    uuids = nil
    begin
      uuids = vsanIntSys.QueryVsanObjectUuidsByFilter(:version => 2)
    rescue RbVmomi::VIM::InvalidRequest => ex
      # This error means we are not able to issue this API call against
      # the host, even though we know it is running 6.0. This must be
      # a plumbing problem in VC. If we can't trust this API call, we
      # also can't trust that evacuation modes are sent to host correctly
      # during RemoveDiskMapping() API calls.
      out['issue'] = RbVmomi::VIM::VsanUpgradeSystemAPIBrokenIssue(
        :msg => "Detected that VC is not passing through API calls to " +
           "ESX correctly. You may want to disconnect and reconnect all " +
           "hosts as a workaround. ",
        :hosts => hosts_props.keys,
      )
      return out
    end
    if opts[:downgrade_format] && !uuids.empty?
      out['issue'] = RbVmomi::VIM::VsanUpgradeSystemV2ObjectsPresentDuringDowngradeIssue(
        :msg => "Detected v2 objects in vSAN datastore. Downgrade not possible.",
        :uuids => uuids,
      )
      return out
    end
  end

  _run_with_rev(conn, "dev") do
    out['missingDG'] = _v2_ondisk_upgrade_restore_check(
      logger, conn, pc, hosts, hosts_props
    )
  end

  out.merge!({
    'type' => 'success',
  })
  return out
end

def _v2_ondisk_upgrade_PerformUpgradePreflightCheck hosts, opts = {}
  logger = NullLogger.new
  conn = hosts.first._connection
  pc = conn.propertyCollector
  res = _ondisk_upgrade_checkcluster logger, conn, pc, hosts, opts
  out = RbVmomi::VIM::VsanUpgradeSystemPreflightCheckResult(
     :issues => res['issue'] ? [res['issue']] : [],
     :diskMappingToRestore => res['missingDG']
  )
  out
end


def _generate_backup_filename hostname
  if OS.windows?
    return ENV['TEMP'] + File::SEPARATOR + hostname
  else
    return "/tmp/" + hostname
  end
end

def _v2_ondisk_upgrade_backup hostname, dg
  diskMapping = {}
  diskMapping['ssd'] = dg.ssd.displayName
  diskMapping['nonSsd'] = dg.nonSsd.map{|x| x.displayName}
  #record disk mapping to temp file
  _write_file(_generate_backup_filename(hostname), diskMapping.to_json)
end

# entities, Array of ManagedEntity
# operations, Array of VIM task operations
# For some cases, user could interrupt RVC command during a VC task execution,
# To avoid the conflict in the secondary run,
# we'd better wait for specified tasks finished.
def _wait_for_pending_tasks conn, entities, operations
  task_manager = conn.serviceContent.taskManager
  recent_tasks = task_manager.recentTask
  if recent_tasks && !recent_tasks.empty?
    pc = conn.propertyCollector
    tasks_props = pc.collectMultiple(recent_tasks,
      'info.entity',
      'info.descriptionId',
      'info.state',
    )
    tasks_props = tasks_props.select do |k, v|
      entities.member?(v['info.entity']) &&
      operations.member?(v['info.descriptionId']) &&
      v['info.state'] != 'success' && v['info.state'] != 'error'
    end
    matched_tasks = tasks_props.keys
    if !matched_tasks.empty?
      puts "#{Time.now}: Waiting for pending tasks"
      results = progress(matched_tasks)
      return results
    end
  end
end


def _v2_ondisk_upgrade_restore status, upgradetask, info, logger, conn, pc, hosts
  wantedDisks = info['wantedDisks']
  host = info['host']
  host_props = info['hosts_props'][host]
  vsanSys = host_props['configManager.vsanSystem']

  # Critical part of missed disk group still exists, including 1 SSD, at least 1 HDD.
  logger.info "Found missed disk group:"
  wantedDisks.each_with_index do |disk, i|
    if i == 0
      logger.info "  SSD: #{disk.displayName}"
    else
      logger.info "  HDD: #{disk.displayName}"
    end
  end

  #XXX, Low level format to support checksum

  status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
    :timestamp => Time.now(),
    :host => host,
    :message => "Restoring disk group from interrupted upgrade run",
  )
  upgradetask.postUpdate(status)

  # Add disk group back
  task = vsanSys.AddDisks_Task(:disk => wantedDisks)
  status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryDiskGroupOp(
    :timestamp => Time.now(),
    :message => "Re-adding disk group",
    :host => host,
    :task => task,
    :diskMapping => info['diskgroup'],
    :operation => 'add'
  )
  upgradetask.postUpdate(status)

  results = {task => _v2_ondisk_upgrade_waitfortask(task)}

  has_errors = _vsan_disk_results_handler(
    logger,
    results,
    "Failed to add these disks as a disk group for vSAN"
  )
  if has_errors
    logger.info "Stop upgrade tool"
    # XXX: Set some error bits
    status.aborted = true
    upgradetask.postUpdate(status)

    # Should notify upgrade thread that
    # missed disk group failed to add back
    # to stop upgrade process
    return has_errors
  end

  # Cleanup backup file
  File.delete(_generate_backup_filename(info['hostname']))
  has_errors
end


def _v2_ondisk_upgrade_restore_check logger, conn, pc, hosts, hosts_props
  break_host = nil
  mapping = nil
#  logger.info "Checking break point in last run."
  hosts.each do |host|
    host_props = hosts_props[host]
    hostname = host_props['name']
    mapping = _read_file(_generate_backup_filename(hostname))
    # Found break point
    if (mapping != nil)
      break_host = host
      mapping = JSON.parse mapping
      break
    end
  end
  if !break_host
    return
  end

  # wait for remove disk mapping task finished on break host,
  # to avoid removing same disk group twice in recovery of 'Ctrl + C'.
  # we don't care the task result here,
  # because if disk mapping was removed, then coming restore logic
  # could cover this;
  # if failed to remove, coming restore logic will be skipped,
  # and this disk mapping will be handled in core loop.
  _wait_for_pending_tasks(
    conn, [break_host], ['host.VsanSystem.removeDiskMapping']
  )

  host_props = hosts_props[break_host]
  vsanSys = host_props['configManager.vsanSystem']
  hostname = host_props['name']
  disks = break_host.filtered_disks_for_vsan(
    :state_filter => /^eligible$/,
    :vsanSystem => vsanSys
  )
  ssd = disks.find{|x| x.displayName == mapping['ssd']}
  hdds = disks.select{|x| mapping['nonSsd'].member?(x.displayName)}
  if !ssd
    return
  end
  # In restore process, some disks in backup file are not claimed in vSAN cluster
  wantedDisks = []
  wantedDisks << ssd
  wantedDisks += hdds
  return {
    'host' => break_host,
    'hostname' => hostname,
    'wantedDisks' => wantedDisks,
    'hosts_props' => hosts_props,
    'diskgroup' => RbVmomi::VIM::VsanHostDiskMapping({
      'ssd' => ssd,
      'nonSsd' => hdds
    })
  }
end


def _update_virsto_config logger, hostname, optionMgr, enable = true
  expect_value = enable ? 1 : 0
  op = enable ? "enable" : "disable"
  virstoKey = "Virsto.Enabled"
  optValues = optionMgr.QueryOptions(:name => virstoKey)
  if optValues[0].key != virstoKey
    raise Exception.new "Cannot find #{virstoKey} in advanced options of host #{hostname}"
  else
    logger.info "Starting #{op} v2 filesystem on host #{hostname}"
    options = {
      virstoKey => expect_value
      #if OptionType is defined as int, we have to use virstoKey => RbVmomi::BasicTypes::Int.new(2048)
    }
    optionMgr.UpdateOptions(:changedValue => options.map do |key, value|
      RbVmomi::VIM::OptionValue(:key => key, :value => value)
    end)
    logger.info "Done #{op} v2 filesystem on host #{hostname}"
  end
  op
end

class RealUpgradeTask
  attr_reader :currentStatus

  def initialize conn, file, rev = nil
    @conn = conn
    @cancelled = false
    @file = file
    @currentStatus = nil
    @rev = rev
  end

  def serialize obj, forVpxd = false
    xml = Builder::XmlMarkup.new(:indent => 0)
    @conn.obj2xml(xml, 'obj', obj.class.wsdl_name, false, x=obj)
    out = xml.target!
    out = out.gsub("xsi:type", "type")
    if forVpxd
      out = out.gsub(' type="', ' xsi:type="')
      if @rev
        ver = @rev
      else
        ver = @conn.latestVersion
      end
      out = out.gsub(/^<obj /, '<obj xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="urn:vim25" versionId="' + ver + '" ')
    end
    out
  end

  def postUpdate info
    if info.is_a?(Exception)
      str = PP.pp(info, "") # XXX
    else
      str = serialize(info, true)
    end
    @currentStatus = str
    if !@file
      return
    end
    open("#{@file}.new", 'w'){|io| io.write str}
    FileUtils.mv("#{@file}.new", @file)
  end

  def isCancelled?
    @cancelled
  end

  def cancel
    @cancelled = true
  end
end

class MockUpgradeTask
  def initialize conn
    @conn = conn
    require 'thread'
    @cancelled = false
    @lock = Mutex.new
    @currentStatus = nil
  end

  def serialize obj
    xml = Builder::XmlMarkup.new(:indent => 0)
    @conn.obj2xml(xml, 'obj', obj.class.wsdl_name, false, x=obj)
    xml.target!.gsub("xsi:type", "type")
  end

  def deserialize xmlstr
    xmlobj = Nokogiri::XML(xmlstr).children.first
    res = @conn.deserializer.deserialize(xmlobj, xmlobj.attr('type'))
    res
  end

  def postUpdate info
    @lock.synchronize do
      if info.is_a?(Exception)
        @currentStatus = info
      else
        @currentStatus = deserialize(serialize(info))
      end
    end
  end

  def isCancelled?
    @cancelled
  end

  def cancel
    @cancelled = true
  end

  def currentStatus
    out = nil
    @lock.synchronize do
      out = @currentStatus
    end
    out
  end
end

def _v2_ondisk_upgrade_backend_StartUpgrade_Task(hosts, opts)
  conn = hosts.first._connection
  upgradetask = MockUpgradeTask.new(conn)

  # Check break point, and restore if necessary
  upgradeThread = Thread.new do
    begin
      _v2_ondisk_upgrade_backend(
        upgradetask, conn, hosts, opts
      )
    rescue Exception => ex
      puts "#{ex.class}: #{ex.message}"
    end
  end

  upgradetask
end

def _v2_ondisk_upgrade_backend_GetStatus(upgradetask)
  upgradetask.currentStatus
end

def _v2_ondisk_upgrade_waitfortask task
  task.wait_until('info.state') { %w(success error).member? task.info.state }
  info = task.info
  case info.state
  when 'success'
    info.result
  when 'error'
    info.error
  end
end

def _v2_ondisk_upgrade_backend upgradetask, _conn, hosts, opts = {}
  conn = _conn.spawn_additional_connection
  hosts = hosts.map{|x| x.dup_on_conn(conn)}
  pc = conn.propertyCollector

  #logger = FileLogger.new("/tmp/rvc_vsan_upgrade.log")
  logger = opts[:logger] || NullLogger.new

  status = RbVmomi::VIM::VsanUpgradeSystemUpgradeStatus(
    :history => [],
    :progress => 0,
    :completed => false,
    :aborted => false,
    :inProgress => true,
  )
  upgradetask.postUpdate(status)

  logger.info "Pre-flight check ..."
  check = _ondisk_upgrade_checkcluster(logger, conn, pc, hosts, opts)
  hosts_props = check['hosts_props']
  if check['type'] != 'success'
    status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryPreflightFail(
      :timestamp => Time.now(),
      :host => nil,
      :message => "Pre-flight check failed",
      :preflightResult => RbVmomi::VIM::VsanUpgradeSystemPreflightCheckResult(
        :issues => [check['issue']],
        :diskMappingToRestore => nil
      )
    )
    status.aborted = true
    upgradetask.postUpdate(status)
    return
  end

  if check['missingDG']
    if opts[:resume_backup]
      has_errors = _v2_ondisk_upgrade_restore(
        status, upgradetask, check['missingDG'], logger, conn, pc, hosts
      )
      if has_errors
        # Failed to restore from last breakpoint
        # upgrade should be stopped
        return
      end
    end
  end

  exclude_hosts = (opts[:exclude_host] || []).uniq

  to_version = opts[:downgrade_format] ? 0 : 2
  # display_version is used to show on the console, we don't wanna user knows version 0.
  display_version = opts[:downgrade_format] ? 1 : 2
  op = opts[:downgrade_format] ? "downgrade" : "upgrade"
  logger.info "Target file system version: v#{display_version}"
  vsan_mode = opts[:allow_reduced_redundancy] ? "ensureObjectAccessibility" : "evacuateAllData"
  logger.info "Disk mapping decommission mode: #{vsan_mode}"

  _run_with_rev(conn, "dev") do
    hosts.each do |host|
      if upgradetask.isCancelled?
        return
      end

      # Upgrade host
      logger.info "Refreshing cluster info, checking status before proceeding"
      check = _ondisk_upgrade_checkcluster(logger, conn, pc, hosts, opts)
      hosts_props = check['hosts_props']
      if check['type'] != 'success'
        status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryPreflightFail(
          :timestamp => Time.now(),
          :host => host,
          :message => "Pre-flight check failed",
          :preflightResult => RbVmomi::VIM::VsanUpgradeSystemPreflightCheckResult(
            :issues => [check['issue']],
            :diskMappingToRestore => nil
          )
        )
        status.aborted = true
        upgradetask.postUpdate(status)
        return
      end
      logger.info "Cluster is in good state, proceeding"
      status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
        :timestamp => Time.now(),
        :host => host,
        :message => "Cluster is still in good state, proceeding ...",
      )
      upgradetask.postUpdate(status)

      host_props = hosts_props[host]
      hostname = host_props['name']

      if exclude_hosts.member?(host)
        # Skip object upgrade if there is host got excluded. PR1267403
        opts[:ignore_objects] = true
        status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
          :timestamp => Time.now(),
          :host => host,
          :message => "Skipping host #{hostname}",
        )
        upgradetask.postUpdate(status)
        logger.info "Skipping host #{hostname}"
        logger.info " "
        next
      end

      vsanSys = host_props['configManager.vsanSystem']
      vsanIntSys = host_props['configManager.vsanInternalSystem']

      # Step 1: Enable VirstoFS on target host
      optionMgr = host_props['configManager.advancedOption']
      _update_virsto_config(
        logger, hostname, optionMgr,
        !opts[:downgrade_format]
      )
      label = opts[:downgrade_format] ? "Disabled" : "Enabled"
      status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
        :timestamp => Time.now(),
        :host => host,
        :message => "#{label} v2 filesystem as default on host #{hostname}",
      )
      upgradetask.postUpdate(status)

      # Step 2: Core loop, evacuate data and remove old vSAN disk group first, and add them back with new FS format
      diskGroups = vsanSys.config.storageInfo.diskMapping
      if diskGroups.empty?
        logger.info "Host #{hostname} has no diskgroup, just skip it"
        status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
          :timestamp => Time.now(),
          :host => host,
          :message => "Host #{hostname} has no diskgroup, just skip it",
        )
        next
      end
      disk_formatted = 0
      diskGroups.each_with_index do |group, i|
        if upgradetask.isCancelled?
          return
        end

        # Only groups without to_version file system should be handled
        current_version = group.ssd.vsanDiskInfo.formatVersion
        if current_version != to_version
          # Take a backup for current disk group
          _v2_ondisk_upgrade_backup(hostname, group)

          logger.info "Removing vSAN disk group:"
          logger.info "Disk group #{i + 1}:"
          logger.info "  SSD: #{group.ssd.displayName}"
          group.nonSsd.each do |hdd|
            logger.info "  HDD: #{hdd.displayName}"
          end
          task = vsanSys.RemoveDiskMapping_Task(
            :mapping => [group],
            :maintenanceSpec => {
              :vsanMode => {
                :objectAction => vsan_mode,
              },
            },
          )
          status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryDiskGroupOp(
            :timestamp => Time.now(),
            :message => "Removing/evacuating disk group",
            :host => host,
            :task => task,
            :diskMapping => group,
            :operation => 'remove'
          )
          upgradetask.postUpdate(status)

          results = {task => _v2_ondisk_upgrade_waitfortask(task)}
          has_errors = _vsan_disk_results_handler(
            logger, results,
            "Failed to remove this disk group from vSAN"
          )
          if has_errors
            logger.info "Stop upgrade tool"
            status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
              :timestamp => Time.now(),
              :host => host,
              :message => "Failed to remove disk group from vSAN, aborting.",
            )
            status.aborted = true
            upgradetask.postUpdate(status)
            return
          end

          if upgradetask.isCancelled?
            return
          end

          #XXX, Low level format to support checksum

          # Add disk group back to vSAN
          logger.info "Re-adding disks to vSAN:"
          logger.info "  SSD: #{group.ssd.displayName}"
          group.nonSsd.each do |hdd|
            logger.info "  HDD: #{hdd.displayName}"
          end
          wantedDisks = []
          wantedDisks << group.ssd
          wantedDisks += group.nonSsd
          task = vsanSys.AddDisks_Task(:disk => wantedDisks)

          status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryDiskGroupOp(
            :timestamp => Time.now(),
            :message => "Re-adding disk group",
            :host => host,
            :task => task,
            :diskMapping => group,
            :operation => 'add'
          )
          upgradetask.postUpdate(status)

          results = {task => _v2_ondisk_upgrade_waitfortask(task)}
          has_errors = _vsan_disk_results_handler(
            logger,
            results,
            "Failed to add these disks as a disk group for vSAN"
          )
          if has_errors
            logger.info "Stop upgrade tool"
            status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
              :timestamp => Time.now(),
              :host => host,
              :message => "Failed to re-add disk group to vSAN, aborting.",
            )
            status.aborted = true
            upgradetask.postUpdate(status)
            return
          end
          # Cleanup backup file
          File.delete(_generate_backup_filename(hostname))
          disk_formatted += 1
        end
      end
      if disk_formatted > 0
        logger.info "Done #{op} host #{hostname}"
        status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
          :timestamp => Time.now(),
          :host => host,
          :message => "Done #{op} host #{hostname}",
        )
        upgradetask.postUpdate(status)
      else
        logger.info "Existing diskgroups are already of v#{display_version} on host #{hostname}"
        status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
          :timestamp => Time.now(),
          :host => host,
          :message => "Existing diskgroups are already of v#{display_version} on host #{hostname}",
        )
        upgradetask.postUpdate(status)
      end
    end
  end

  status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
    :timestamp => Time.now(),
    :host => nil,
    :message => "Done with disk format #{op} phase",
  )
  upgradetask.postUpdate(status)

  logger.info "Done disk format #{op}"
  if opts[:ignore_objects] || opts[:downgrade_format]
    # Ignore object upgrade, just stop upgrade tool and disk format is done
    logger.info "Ignore objects #{op}"
    logger.info "Done vSAN #{op}"
    status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
      :timestamp => Time.now(),
      :host => nil,
      :message => "Not performing any object version conversion",
    )
    status.completed = true
    upgradetask.postUpdate(status)
    return
  end

  # Phase 3, object version upgrade
  _run_with_rev(conn, "dev") do
    host = hosts_props.keys.first
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
    total = vsanIntSys.QueryVsanObjectUuidsByFilter(:version => 0)
    obj_num = total.length
    status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
      :timestamp => Time.now(),
      :host => nil,
      :message => "There are #{obj_num} v1 objects that require upgrade"
    )
    upgradetask.postUpdate(status)
    logger.info "There are #{obj_num} v1 objects that require upgrade"
    # Loop to find v1 object and convert, 3000 objects per operation
    done_num = 0
    uuids = total.pop(3000)
    begin
      while !uuids.empty?
        results = vsanIntSys.UpgradeVsanObjects(:uuids => uuids, :newVersion => 2)
        if !results.empty?
          done_num += (uuids.length - results.length)
          status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
            :timestamp => Time.now(),
            :host => nil,
            :message => "Object upgrade progress: %d upgraded, %d left" % [
              done_num, obj_num - done_num
            ]
          )
          upgradetask.postUpdate(status)
          status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
            :timestamp => Time.now(),
            :host => nil,
            :message => "Failed to upgrade %d vSAN objects" % [
              results.length
            ]
          )
          upgradetask.postUpdate(status)
          results.each do |result|
            text = "uuid #{result.uuid} : "
            if result.failureReason && !result.failureReason.empty?
              messages = result.failureReason.map{|x| x.message}
              text += "#{messages}"
            end
            #TODO, Currently we display 'message' of LocalizableMessage to customer
            # Will be fixed if the message is not enough
            status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
              :timestamp => Time.now(),
              :host => nil,
              :message => text
            )
            upgradetask.postUpdate(status)
          end
          logger.info "Object upgrade progress => #{done_num} finished"
          logger.info "Failed to upgrade #{results.length} vSAN objects"
          results.each do |result|
            text = "uuid #{result.uuid} : "
            if result.failureReason && !result.failureReason.empty?
              messages = result.failureReason.map{|x| x.message}
              text += "#{messages}"
            end
            #TODO, Currently we display 'message' of LocalizableMessage to customer
            # Will be fixed if the message is not enough
            logger.info text
          end
          # Encountered error, stopping upgrade tool.
          status.aborted = true
          upgradetask.postUpdate(status)
          return
        else
          done_num += uuids.length
          status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
            :timestamp => Time.now(),
            :host => nil,
            :message => "Object upgrade progress: %d upgraded, %d left" % [
              done_num, obj_num - done_num
            ]
          )
          upgradetask.postUpdate(status)
          logger.info "Object upgrade progress => #{done_num} finished, #{obj_num - done_num} left"
          uuids = total.pop(3000)
        end
      end
    rescue Exception => e
      logger.info "Failed to upgrade vSAN objects:"
      logger.info "#{e.class}: #{e.message}"
      upgradetask.postUpdate(e)
      return
    end
    logger.info "Done objects upgrade, totally #{obj_num} objects have been upgraded"
    status.history << RbVmomi::VIM::VsanUpgradeSystemUpgradeHistoryItem(
      :timestamp => Time.now(),
      :host => nil,
      :message => "Object upgrade completed: %d upgraded" % [
        obj_num
      ]
    )
    status.completed = true
    upgradetask.postUpdate(status)
  end

rescue Exception => ex
  upgradetask.postUpdate(ex)
  raise
end

load File.join(File.dirname(__FILE__), 'vsanmgmt_disk_mgmt.api.txt')
load File.join(File.dirname(__FILE__), 'vsanmgmt.api.txt')
class ::RbVmomi::VIM

  VSAN_API_VC_ENDPOINT = '/vsanHealth'
  VSAN_API_ESXI_ENDPOINT = '/vsan'

  VSAN_VMODL_NAMESPACE = "urn:vsan"
  VIM_VMODL_NAMESPACE = "urn:vim25"

  VSAN_VMODL_VERSION_XML_URI = "/sdk/vsanServiceVersions.xml"
  VIM_VMODL_VERSION_XML_URI = "/sdk/vimServiceVersions.xml"
  def initialize opts
    super opts
    @vsanMgmt = nil
  end

  def vsanMgmt
    # Only maintain one connection to VC SIMS server
    ns, rev = getLatestVmodlInfo(self)
    if @vsanMgmt == nil
      @vsanMgmt = VIM.new(
        :host => @opts[:host],
        :port => self.vsan_standalone_mode ? 8006 : 443,
        :insecure => true,
        :ns => ns,
        :ssl => true,
        :rev => rev,
        :path => '/vsanHealth',
        :pcexist => false
      )
      @vsanMgmt.cookie = @cookie
      @vsanMgmt.debug = @debug
    end
    # Refresh session cookie
    if @vsanMgmt.cookie != @cookie
      @vsanMgmt.cookie = @cookie
    end
    return @vsanMgmt
  end
  #
  # Get the VMODL version by checking the existence of vSAN namespace.
  def getLatestVmodlInfo(conn)
    vsanVersion = getServiceVersionXml(conn,
      VSAN_VMODL_NAMESPACE, VSAN_VMODL_VERSION_XML_URI)
    if vsanVersion
      return VSAN_VMODL_NAMESPACE, vsanVersion
    else
      vimVersion = getServiceVersionXml(conn,
        VIM_VMODL_NAMESPACE, VIM_VMODL_VERSION_XML_URI)
      abort "Cannot fetch the #{VIM_VMODL_NAMESPACE} service version on #{conn.host}!" unless vimVersion
      return VIM_VMODL_NAMESPACE, vimVersion
    end
  end

  def getServiceVersionXml(conn, ns, serviceXmlUri)
    serviceName = ns.split(":")[1]
    versionXml = open(
      'https://' + conn.host + serviceXmlUri,
      { ssl_verify_mode: conn.http.verify_mode }
    )
    versionXmlDoc = Nokogiri::XML(versionXml)
    return versionXmlDoc.xpath('//name')[0].text == ns ?
      versionXmlDoc.xpath('//version')[0].text : nil
  rescue
    return nil
  end
end

def _is_upgrade_api_supported cluster
  if not cluster.is_a?(RbVmomi::VIM::ClusterComputeResource)
    # Upgrade API doesn't support non cluster types
    return false
  end
  vusEx = _get_upgrade_systemex(cluster._connection)
  begin
    vusEx.RetrieveSupportedVsanFormatVersion(:cluster => cluster)
  rescue Exception => ex
    return false
  end
  return true
end

def _get_vsan_system conn, vsanSystem
  return VIM::HostVsanSystem(conn.vsanMgmt, vsanSystem._ref)
end

def _get_upgrade_system conn
  return VIM::VsanUpgradeSystem(conn.vsanMgmt, 'vsan-upgrade-system2')
end

def _get_upgrade_systemex conn
  return VIM::VsanUpgradeSystemEx(conn.vsanMgmt, 'vsan-upgrade-systemex')
end

def _get_vsan_systemex conn, id
  return VIM::VsanSystemEx(conn.vsanMgmt, 'vsanSystemEx-' + String(id))
end

def _log_upgrade_history_item conn, logger, item, hosts_props
  key = item.message
  if key == "com.vmware.vsan.diskconversion.events.restore"
    host = item.host.dup_on_conn(conn)
    logger.info "Restore diskgroup on host #{hosts_props[host]['name']}"
  elsif key == "com.vmware.vsan.diskconversion.events.migrationfail"
    logger.info "Failed to migrate vsanSparse objects."
  elsif key == "com.vmware.vsan.diskconversion.events.skiphost"
    host = item.host.dup_on_conn(conn)
    logger.info "Skip host #{hosts_props[host]['name']} from disk format conversion."
  elsif key == "com.vmware.vsan.diskconversion.events.statuscheck"
    logger.info "Check cluster status for disk format conversion."
  elsif key == "com.vmware.vsan.diskconversion.events.updatesetting"
    host = item.host.dup_on_conn(conn)
    logger.info "Update vSAN system settings on host #{hosts_props[host]['name']}"
  elsif key == "com.vmware.vsan.diskconversion.events.removefail"
    host = item.host.dup_on_conn(conn)
    logger.info "Failed to remove diskgroup on host #{hosts_props[host]['name']} from vSAN."
  elsif key == "com.vmware.vsan.diskconversion.events.addfail"
    host = item.host.dup_on_conn(conn)
    logger.info "Failed to add diskgroup back to vSAN on host #{hosts_props[host]['name']}."
  elsif key == "com.vmware.vsan.diskconversion.events.formathostdone"
    host = item.host.dup_on_conn(conn)
    logger.info "Disk format conversion is done on host #{hosts_props[host]['name']}."
  elsif key == "com.vmware.vsan.diskconversion.events.noneed"
    host = item.host.dup_on_conn(conn)
    logger.info "Skip host #{hosts_props[host]['name']} from disk format conversion due to not needed."
  elsif key == "com.vmware.vsan.diskconversion.events.formatdone"
    logger.info "Disk format conversion is done."
  elsif key == "com.vmware.vsan.diskconversion.events.objectcheck"
    logger.info "Check existing objects on vSAN."
  elsif key == "com.vmware.vsan.diskconversion.events.objecterror"
    logger.info "Failed to convert objects on vSAN."
  elsif key == "com.vmware.vsan.diskconversion.events.objectdone"
    logger.info "Object conversion is done."
  else
    logger.info key
  end
end
