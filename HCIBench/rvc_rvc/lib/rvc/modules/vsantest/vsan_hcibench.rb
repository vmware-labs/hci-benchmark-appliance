# Copyright (c) 2013 VMware, Inc.  All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
require 'pp'
require 'erb'
require 'rvc/vim'
require 'json'
require 'time'
load 'rvc/lib/vsangeneric.rb'

VIM::ClusterComputeResource

$rvc_json_use_oj = false
# begin
  # require 'oj'
# rescue LoadError
  # $rvc_json_use_oj = false
# end
$currentPath = File.dirname(__FILE__)
$obsPath = $currentPath + "/observer"
$analyser_lib_dirname = $obsPath

def rvc_load_json x
  if $rvc_json_use_oj
    Oj.load(x)
  else
    JSON.load(x)
  end
end

class RbVmomi::BasicTypes::DataObject
  def [] x
    _get_property(x.to_sym)
  end

  def []= sym, val
    _set_property(sym.to_sym, val)
  end

  def to_json(*args)
    props.to_json
  end

  def to_dict
    Hash[@props.map do |k,v|
      if v.is_a?(RbVmomi::BasicTypes::DataObject)
        v = v.to_dict
      end
      [k.to_s, v]
    end]
  end
end



$vsanUseGzipApis = true

def is_uuid str
  str =~ /[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/
end

opts :clear_disks_cache do
  summary "Clear cached disks information"
end

def clear_disks_cache
  $disksCache = {}
end

opts :enable_vsan_on_cluster do
  summary "Enable VSAN on a cluster"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource
  opt :disable_storage_auto_claim, "Disable auto disk-claim", :type => :boolean
end

def enable_vsan_on_cluster cluster, opts
  conn = cluster._connection
  _run_with_rev(conn, "dev") do
    spec = VIM::ClusterConfigSpecEx(
      :vsanConfig => {
        :enabled => true,
        :defaultConfig => {
          :autoClaimStorage => (!(opts[:disable_storage_auto_claim] || false)),
        }
      }
    )
    task = cluster.ReconfigureComputeResource_Task(:spec => spec, :modify => true)
    progress([task])
    childtasks = task.child_tasks
    if childtasks && childtasks.length > 0
      progress(childtasks)
    end
  end
end

opts :disable_vsan_on_cluster do
  summary "Disable VSAN on a cluster"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource
end

def disable_vsan_on_cluster cluster
  conn = cluster._connection
  _run_with_rev(conn, "dev") do
    spec = VIM::ClusterConfigSpecEx(
      :vsanConfig => {
        :enabled => false,
      }
    )
    model = VsanModel.new([cluster])
    if !model.basic['witness_info'].nil?
      vsanSystem = model.basic['hosts_props'][model.basic['witness_info'][:host]]['configManager.vsanSystem']
      witness_task = vsanSystem.UpdateVsan_Task(:config => {
          :enabled => false,
        }
      )
      progress([witness_task])
      childtasks = witness_task.child_tasks
      if childtasks && childtasks.length > 0
        progress(childtasks)
      end
    end
    task = cluster.ReconfigureComputeResource_Task(:spec => spec, :modify => true)
    progress([task])
    childtasks = task.child_tasks
    if childtasks && childtasks.length > 0
      progress(childtasks)
    end
  end
end

opts :cluster_change_autoclaim do
  summary "Enable/Disable autoclaim on a VSAN cluster"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource
  opt :enable, "Enable auto-claim", :type => :boolean
  opt :disable, "Disable auto-claim", :type => :boolean
end

def cluster_change_autoclaim cluster, opts
  conn = cluster._connection
  if opts[:enable] && opts[:disable]
    err "Can only enable or disable, not both"
  end
  if !opts[:enable] && !opts[:disable]
    err "Please pass either --enable or --disable"
  end
  _run_with_rev(conn, "dev") do
    spec = VIM::ClusterConfigSpecEx(
      :vsanConfig => {
        :defaultConfig => {
          :autoClaimStorage => opts[:enable] ? true : false,
        }
      }
    )
    task = cluster.ReconfigureComputeResource_Task(:spec => spec, :modify => true)
    progress([task])
    childtasks = task.child_tasks
    if childtasks && childtasks.length > 0
      progress(childtasks)
    end
    childtasks = task.child_tasks
    if childtasks && childtasks.length > 0
      progress(childtasks)
    end
    model = VsanModel.new([cluster])
    if !model.basic['witness_info'].nil?
      vsanSystem = model.basic['hosts_props'][model.basic['witness_info'][:host]]['configManager.vsanSystem']
      witness_task = vsanSystem.UpdateVsan_Task(:config => {
        :storageInfo => {
            :autoClaimStorage => opts[:enable] ? true : false,
          }
        }
      )
      progress([witness_task])
      childtasks = witness_task.child_tasks
      if childtasks && childtasks.length > 0
        progress(childtasks)
      end
    end
  end
end


opts :host_consume_disks do
  summary "Consumes all eligible disks on a host"
  arg :host_or_cluster, nil, :lookup => [VIM::ComputeResource, VIM::HostSystem], :multi => true
  opt :filter_ssd_by_model, "Regex to apply as SSD model filter", :type => :string
  opt :filter_hdd_by_model, "Regex to apply as HDD model filter", :type => :string
end

def host_consume_disks hosts_or_clusters, opts
  conn = hosts_or_clusters.first._connection
  hosts = []
  hosts_or_clusters.each do |host_or_cluster|
    if host_or_cluster.is_a?(VIM::HostSystem)
      hosts << host_or_cluster
    else
      hosts += host_or_cluster.host
    end
  end
  if opts[:filter_ssd_by_model]
    opts[:filter_ssd_by_model] = /#{opts[:filter_ssd_by_model]}/
  end
  if opts[:filter_hdd_by_model]
    opts[:filter_hdd_by_model] = /#{opts[:filter_hdd_by_model]}/
  end
  tasks = []
  results = {}
  _run_with_rev(conn, "dev") do
    tasks = hosts.map do |host|
      host.consume_disks_for_vsan(opts)
    end.compact
    if tasks.length > 0
      results = progress(tasks)
      pp results.values.flatten.map{|x| x.error}.compact
    else
      puts "No disks were consumed."
    end
    $claimResults = results
  end
  $disksCache = {}
end

opts :host_wipe_vsan_disks do
  summary "Wipes content of all VSAN disks on hosts, by default wipe all disk groups"
  arg :hosts, nil, :lookup => VIM::HostSystem, :multi => true
  opt :disk, "Disk's canonical name, as identifier of disk to be wiped", :type => :string, :multi => true
  opt :interactive, "Select disks to wipe from given disk list, cannot be set together with parameter 'disks'", :type => :boolean
  opt :allow_reduced_redundancy, "Removes the need for disks worth of free space, by allowing reduced redundancy during disk wiping", :type => :boolean
  opt :no_action, "Take no action to protect data during disk wiping", :type => :boolean
  opt :force, "Forcely wipe disks without any confirmation", :type => :boolean
end

def _show_disks disks_or_groups
  t = Terminal::Table.new()
  t << ['Index', 'DisplayName', 'isSSD']
  t.add_separator
  index = 0
  disks_or_groups.each do |x|
    if x.is_a?(VIM::VsanHostDiskMapping)
      # Disk group
      t << [
        index += 1,
        x.ssd.canonicalName,
        'SSD',
      ]
      x.nonSsd.each do |hdd|
        t << [
          index += 1,
          hdd.canonicalName,
          'MD',
        ]
      end
    else
      t << [
        index += 1,
        x.canonicalName,
        x.ssd ? 'SSD' : 'MD'
      ]
    end
    if x != disks_or_groups.last
      t.add_separator
    end
  end
  puts t
end

# Accpet user input index of disks,
# help to decide which disks user want to remove.
# disks: Array of HostScsiDisk
def _disk_selection_question disks
  regex = /^[1-9][0-9]*$/
  inputs = []
  begin
    puts "Please input index of disks to be wiped, use comma to separate, input 'abort' to break:"
    input = $stdin.gets.chomp
    input.strip!
    if input.casecmp('abort') == 0
      inputs = []
      return inputs
    end
    inputs = input.split(',').map{|x| x.strip}.uniq
    inputs = inputs.select{|x| x =~ regex}
    inputs = inputs.map{|x| x.to_i}
    if !inputs.empty?
      # Verify user input indexes
      # all input indexes must exist in entity array
      invalid_inputs = inputs.select{|x| !disks[x - 1]}
      if invalid_inputs.length > 0
        puts "Detected invalid index of disks: #{invalid_inputs}, please try again:"
        inputs = []
      end
    end
  end while inputs.empty?
  inputs = inputs.sort
  return inputs.map{|x| disks[x - 1]}
end

# Check user given disk list,
# to decide which entity should be removed,
# with following conditions:
# 1. If an SSD was picked, take disk group finally;
# 2. If all HDDs of an DG were picked, also take disk group finally;
# 3. take left HDDs
def _process_disks_to_remove disk_groups, selected_disks
  entity_to_remove = []
  disk_groups.each do |dg|
    # SSD was picked
    if selected_disks.member?(dg.ssd)
      entity_to_remove << dg
    else
      hdds = selected_disks.select{|x| dg.nonSsd.member?(x)}
      # All HDDs of DG were picked
      if hdds.length == dg.nonSsd.length
        entity_to_remove << dg
      else
        # Take left HDDs
        entity_to_remove += hdds
      end
    end
  end
  return entity_to_remove
end

def host_wipe_vsan_disks hosts, opts
  selected_disks = opts[:disk] || []
  selected_disks.uniq
  if opts[:interactive] && !selected_disks.empty?
    puts ""
    puts "Interactive mode cannot be used together with"
    puts "user specified disks"
    return
  end
  hosts = hosts.uniq
  if !selected_disks.empty? && hosts.length > 1
    puts ""
    puts "User specify disks to wipe, can only support"
    puts "single host mode"
    return
  end

  vsan_mode = "evacuateAllData"
  if opts[:no_action]
    vsan_mode = "noAction"
  end
  if opts[:allow_reduced_redundancy]
    vsan_mode = "ensureObjectAccessibility"
  end

  conn = hosts.first._connection
  pc = conn.propertyCollector
  hosts_props = pc.collectMultiple(hosts,
    'name',
    'configManager.vsanSystem',
  )
  _run_with_rev(conn, "dev") do
    hosts.each do |host|
      host_props = hosts_props[host]
      host_name = host_props['name']
      vsan = host_props['configManager.vsanSystem']

      puts "#{Time.now}: Checking status on host #{host_name}"

      config = vsan.config
      # Cannot remove disks on a host with VSAN and auto-claim all enabled.
      if config.storageInfo.autoClaimStorage
        if config.enabled
          puts ""
          puts "Disks cannot be wiped when storage auto claim mode is enabled"
          puts "Please disable it and try again"
          puts "Wipe disk operation is aborted"
          return
        end
      end
      disk_groups = config.storageInfo.diskMapping
      if disk_groups.empty?
        # No disk group, no need to proceed.
        puts "#{Time.now}: There is no VSAN disk on host #{host_name}, skip it"
        next
      end
      puts "#{Time.now}: Done checking status on host #{host_name}"
      puts ""

      disks = []
      disk_groups.map do |dg|
        disks << dg.ssd
        disks += dg.nonSsd
      end

      entity_to_remove = []
      if opts[:interactive]
        puts "VSAN disks on host #{host_name}:"
        _show_disks(disk_groups)
        puts ""

        selected_disks = _disk_selection_question(disks)
        if selected_disks.empty?
          return
        end
        entity_to_remove = _process_disks_to_remove(disk_groups, selected_disks)
      elsif !selected_disks.empty?
        disk_names = disks.map{|x| x.canonicalName}
        invalid_disks = selected_disks.select{|x| !disk_names.member?(x)}
        if invalid_disks.length > 0
          puts ""
          puts "Following specified disks cannot be found on host #{host_name}:"
          puts invalid_disks
          # Stop disk wiping because invalid disk specified
          puts "Wipe disk operation is aborted"
          return
        end
        selected_disks = disks.select{|x| selected_disks.member?(x.canonicalName)}
        entity_to_remove = _process_disks_to_remove(disk_groups, selected_disks)
      else
        # Neither interactive mode, nor given disks
        # All disk groups should be involved by default
        entity_to_remove = disk_groups
      end

      puts "Disks to be wiped:"
      _show_disks(entity_to_remove)
      # If force wipe was not specified, we need to confirm with user,
      # because wipe disk groups is a destructive operation
      if _is_v6_compatible(conn)
        puts "#{Time.now}: Data evacuation mode during disk wiping: #{vsan_mode}"
        case vsan_mode
        when "noAction"
          puts "No data protection action will be taken during disk wiping,"
          puts "which may cause data lost in VSAN"
        when "ensureObjectAccessibility"
          puts "Data compliance may be broken, to speed up data evacuation,"
          puts "but data won't get lost"
        when "evacuateAllData"
          puts "All data will be evacuated to other disks, to keep data's"
          puts "integrity and compliance"
        end
      end
      if !opts[:force]
        proceed = _questionnaire(
          "Are you willing to wipe above disks?[Y/N]",
          ['y', 'n'],
          'y'
        )
        if !proceed
          puts "User cancelled disk wiping operation"
          return
        end
      end

      entity_to_remove.each do |entity|
        task = nil
        if entity.is_a? (VIM::VsanHostDiskMapping)
          # remove disk group
          puts "#{Time.now}: Removing VSAN disk group:"
          puts "Disk group:"
          puts "  SSD: #{entity.ssd.displayName}"
          entity.nonSsd.each do |hdd|
            puts "  HDD: #{hdd.displayName}"
          end
          if _is_v6_compatible(conn)
            task = vsan.RemoveDiskMapping_Task(
              :mapping => [entity],
              :maintenanceSpec => {
                :vsanMode => {
                  :objectAction => vsan_mode,
                },
              },
            )
          else
            task = vsan.RemoveDiskMapping_Task(
              :mapping => [entity],
            )
          end
          results = progress([task])
          has_errors = _vsan_disk_results_handler(
            SimpleLogger.new,
            results,
            "Failed to remove this disk group from VSAN"
          )
          if has_errors
            puts "#{Time.now}: Wipe disk operation is aborted"
            return
          end
        else
          # remove disk
          puts "#{Time.now}: Removing VSAN disk: #{entity.displayName}"
          if _is_v6_compatible(conn)
            task = vsan.RemoveDisk_Task(
              :disk => [entity],
              :maintenanceSpec => {
                :objectAction => vsan_mode,
              }
            )
          else
            task = vsan.RemoveDisk_Task(
              :disk => [entity],
            )
          end
          results = progress([task])
          has_errors = _vsan_disk_results_handler(
            SimpleLogger.new,
            results,
            "Failed to remove disk #{entity.canonicalName} from VSAN"
          )
          if has_errors
            puts "#{Time.now}: Wipe disk operation is aborted"
            return
          end
        end
      end
      puts "#{Time.now}: Done wiping disks on host #{host_name}"
    end
  end
end

opts :host_info do
  summary "Print VSAN info about a host"
  arg :host, nil, :lookup => VIM::HostSystem
end

def host_info host
  conn = host._connection
  pc = conn.propertyCollector
  _run_with_rev(conn, "dev") do
    model = VsanModel.new(
      [host],
      [],
      :allow_multiple_clusters => true
    )
    host_data = model.cluster_config_info[host]
    info = _view_host_info(host, host_data, "")
    info.each do |prop|
      puts prop
    end
  end
end

opts :cluster_info do
  summary "Print VSAN config info about a cluster or hosts"
  arg :hosts_and_clusters, nil, :lookup => [VIM::HostSystem, VIM::ClusterComputeResource], :multi => true
end

def cluster_info hosts_and_clusters
  conn = hosts_and_clusters.first._connection
  pc = conn.propertyCollector
  result = {}
  _run_with_rev(conn, "dev") do
    hosts_props_names = [
      'configManager.networkSystem',
      'runtime.inMaintenanceMode',
    ]
    model = VsanModel.new(
      hosts_and_clusters,
      hosts_props_names,
      :allow_multiple_clusters => true
    )
    hosts = model.basic['connected_hosts']
    hosts_props = model.basic['hosts_props']

    cluster_config_info = model.cluster_config_info
    cluster_config_info.each do |host, host_data|
      result[host] = _view_host_info(host, host_data, "  ", model.basic['witness_info'])
    end

    hosts.each do |host|
      puts "Host: #{hosts_props[host]['name']}"
      info = result[host]
      if info
        info.each do |prop|
          puts prop
        end
        puts ""
      end
    end

    fault_domain = {}
    allClusters = hosts_and_clusters.all?{|x| x.is_a?(VIM::ClusterComputeResource)}
    isSingleCluster = hosts_and_clusters.length == 1 && allClusters
    if _is_v6_compatible(conn) && isSingleCluster
      cluster = hosts_and_clusters.first
      _run_with_rev(conn, "dev") do
        vsanHostConfig = cluster.configurationEx.vsanHostConfig
        # faultDomainInfo could be in three cases: nil(55u1), name = ""(not configured) or name = VALID(configured)
        # treat case 1 and 2 as the same, not configured
        vsanHostConfig.each do |x|
          if x.faultDomainInfo && x.faultDomainInfo.name == ''
            x.faultDomainInfo = nil
          end
        end
        fault_domain = vsanHostConfig.group_by{|x| x.faultDomainInfo}
      end
    end
    puts ""
    if !isSingleCluster
      # don't print anything
    elsif fault_domain.empty? || fault_domain.keys == [nil]
      # empty fault_domain or only one key nil, means not configured
      puts "No Fault Domains configured in this cluster"
    else
      puts "Cluster has fault domains configured:"
      fault_domain.each do |fd, configs|
        nodes = configs.map{|x| hosts_props[x.hostSystem]['name']}
        fd_name = fd ? fd.name : "Not Configured"
        puts "#{fd_name}: #{nodes.join(", ")}"
      end
      if !model.basic['witness_info'].nil?
        puts "Preferred fault domain: #{model.basic['witness_info'][:preferredFdName]}"
        puts "Preferred fault domain UUID: #{model.basic['witness_info'][:preferredFdUuid]}"
	if !model.basic['witness_info'][:host].nil?
          puts "Witness Host: #{model.basic['witness_info'][:host][:name]}"
        end
      end

    end
  end
end


def _collect_disks_info hosts, opts = {}
  conn = hosts.first._connection
  pc = conn.propertyCollector
  props = [
    'name',
    'configManager.storageSystem',
    'configManager.vsanSystem',
    'configManager.vsanInternalSystem',
    'datastore',
    'runtime.connectionState'
  ]
  if opts[:host_prop_names]
    props = (props + opts[:host_prop_names]).uniq
  end
  hosts_props = pc.collectMultiple(hosts, *props)
  connected_hosts = hosts_props.select do |k,v|
    v['runtime.connectionState'] == 'connected'
  end.keys
  out = {}
  _run_with_rev(conn, "dev") do
    hosts.each do |host|
      out[host] = {
        "host_props" => hosts_props[host],
      }
    end
    threads = connected_hosts.map do |_host|
      puts "#{Time.now}: Gathering disk information for host #{hosts_props[_host]['name']}"
      Thread.new do
        c1 = conn.spawn_additional_connection
        pc2 = pc.dup_on_conn(c1)
        host = _host.dup_on_conn(c1)

        host_props = hosts_props[host]
        host_name = host_props['name']

        dsList = host_props['datastore']
        dsListProps = pc2.collectMultiple(dsList, 'summary', 'name', 'info')
        vmfsDsList = dsListProps.select do |ds, props|
          props['summary'].type == "VMFS"
        end.keys

        _vsan = host_props['configManager.vsanSystem']
        vsan = _vsan.dup_on_conn(c1)
        disks = vsan.QueryDisksForVsan()
        storcore = host.esxcli.storage.core
        partitions = storcore.device.partition.list
        partitions.each do |part|
          types = {
            0xfb => 'vmfs',
            0xfc => 'coredump',
            0xfa => 'vsan',
            0x0 => 'unused',
            0x6 => 'vfat',
          }
          part['typeStr'] = types[part.Type] || part.Type
          if part['typeStr'] == "vmfs"
            part['vmfsDs'] = vmfsDsList.select do |vmfsDs|
              props = dsListProps[vmfsDs]
              props['info'].vmfs.extent.any? do |ext|
                ext.diskName == part.Device && part.Partition == ext.partition
              end
            end
          end
        end
        if opts[:show_adapters]
          paths = storcore.path.list
          adapters = storcore.adapter.list
        end
        _vsanIntSys = host_props['configManager.vsanInternalSystem']
        vsanIntSys = _vsanIntSys.dup_on_conn(c1)
        vsandisks = vsanIntSys.query_physical_vsan_disks(:props => [
          'uuid',
          'isSsd',
          'owner',
          'formatVersion',
          'publicFormatVersion',
        ])
        vsandisks = vsandisks.values.group_by{|x| x['owner']}
        vsansys_props = pc2.collectMultiple([vsan],
          'config.clusterInfo',
        )
        vsandisks = vsandisks[vsansys_props[vsan]['config.clusterInfo'].nodeUuid] || []
        disks.each do |disk|
          disk['partition'] = partitions.select do |x|
            x.Device == disk.disk.canonicalName && x.Type != 0
          end
          formatVersion = "N/A"
          if disk.vsanUuid
            vsandisk = vsandisks.find{|x| x['uuid'] == disk.vsanUuid}
            if vsandisk
              formatVersion = _marshal_vsan_version(vsandisk['formatVersion'])
            end
          end
          disk['vsanFormatVersion'] = formatVersion
          if opts[:show_adapters]
            diskPaths = paths.select{|x| x.Device == disk.disk.canonicalName}
            diskAdapters = diskPaths.map{|x| x.Adapter}.uniq
            diskAdapters = adapters.select{|x| diskAdapters.member?(x.HBAName)}
            disk['adapters'] = diskAdapters
          end
        end # disks.each
        out[_host] = {
          "disks" => disks,
          "vsandisks" => vsandisks,
          "adapters" => adapters,
          "paths" => paths,
          "partitions" => partitions,
          "vmfsDsList" => vmfsDsList,
          "dsListProps" => dsListProps,
          "dsList" => dsList,
          "host_props" => host_props,
        }
      end # Thread.new
    end
    threads.each{|t| t.join}
    puts "#{Time.now}: Done gathering disk information"
  end
  out
end

opts :disks_info do
  summary "Print physical disk info about a host"
  arg :host, nil, :lookup => VIM::HostSystem, :multi => true
  opt :show_adapters, "Show adapter information", :type => :boolean
end

def disks_info hosts, opts = {}
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

    dsList = host_props['datastore']
    dsListProps = host_info['dsListProps']
    vmfsDsList = host_info['vmfsDsList']

    disks = host_info['disks']
    partitions = host_info['partitions']
    paths = host_info['paths']
    adapters = host_info['adapters']
    vsandisks = host_info['vsandisks']

    t = Terminal::Table.new()
    t << ['DisplayName', 'isSSD', 'Size', 'State']
    needSep = true
    disks.each do |disk|
      capacity = disk.disk.capacity
      size = capacity.block * capacity.blockSize
      sizeStr = "#{size / 1024**3} GB"
      state = disk.state
      t.add_separator
      needSep = false
      if state != 'eligible' && disk.error
        state += " (#{disk.error.localizedMessage})"
        state += "\n"
        if disk.error.fault.is_a?(VIM::DiskHasPartitions)
          state += "\n"
          state += "Partition table:\n"
          disk['partition'].each do |x|
            partSize = x.Size.to_f / 1024**3
            type = x['typeStr']
            state += "#{x.Partition}: %.2f GB, type = #{type}" % partSize
            if type == "vmfs"
              vmfsStr = x['vmfsDs'].map do |vmfsDs|
                "'#{dsListProps[vmfsDs]['name']}'"
              end.join(", ")
              if vmfsStr
                state += " (#{vmfsStr})"
              end
            end
            state += "\n"
          end
          needSep = true
        end
      else
        state += "\n"
      end

      if disk.state == 'inUse'
        formatVersion = disk['vsanFormatVersion']
        state += "VSAN Format Version: v#{formatVersion}\n"
      end
      if opts[:show_adapters]
        diskAdapters = disk['adapters']
        state += "\nAdapters:\n"
        diskAdapters.each do |adap|
          descr = adap.Description.split(" ", 2).last
          state += "#{adap.HBAName} (#{adap.Driver})\n"
          state += "  #{descr}\n"
        end
      end
      t << [
        [
          disk.disk.displayName,
          [
            disk.disk.vendor,
            disk.disk.model
          ].compact.map{|x| x.strip}.join(" ")
        ].join("\n"),
        disk.disk.ssd ? "SSD" : "MD",
        sizeStr,
        state
      ]
    end
    puts t
    if hosts.length > 0
      puts ""
    end
  end
end

def _marshal_vsan_version vsanVersion
  if !vsanVersion
    return 1
  end
  convertedVersionMap = {
    0 => '1',
    2 => '2',
    3 => '2.5',
    4 => '3',
  }
  return convertedVersionMap[vsanVersion]
end

def _view_host_info host, host_data, prefix = '', witness_info = nil
  host_props = host_data['host_props']
  config = host_data['vsan.config']
  info = []
  line = lambda{|x| info << "#{prefix}#{x}" }
  product = host_props['config.product']
  line.call "Product: #{product.fullName}"
  line.call "VSAN enabled: %s" % (config.enabled ? "yes" : "no")
  if !config.enabled
    return info
  end
  status = host_data['vsanHostStatus']
  line.call "Cluster info:"
  line.call "  Cluster role: #{status.nodeState.state}"
  line.call "  Cluster UUID: #{config.clusterInfo.uuid}"
  line.call "  Node UUID: #{config.clusterInfo.nodeUuid}"
  if !witness_info.nil? && witness_info[:nodeUuid] == config.clusterInfo.nodeUuid
    line.call "  Node Type: Witness"
  end
  line.call "  Member UUIDs: #{status.memberUuid} (#{status.memberUuid.length})"

  decom_state = host_props['rvc_is_nodedecom']
  if decom_state
    line.call "Node evacuated: yes (won't accept any new components)"
  else
    line.call "Node evacuated: no"
  end
  line.call "Storage info:"
  line.call "  Auto claim: %s" % (config.storageInfo.autoClaimStorage ? "yes" : "no")
  line.call "  Disk Mappings:"
  if config.storageInfo.diskMapping.length == 0
    line.call "    None"
  else
    config.storageInfo.diskMapping.each do |mapping|
      ssdDisk = mapping.ssd
      capacity = ssdDisk.capacity
      size = capacity.block * capacity.blockSize
      formatVersion = "N/A"
      if product.version >= '6.0.0' && ssdDisk.vsanDiskInfo
        detail = ssdDisk.vsanDiskInfo
        formatVersion = "v#{_marshal_vsan_version(detail.formatVersion)}"
      elsif product.version < '6.0.0'
        # Only v1 disk groups exist on node before 6.0
        formatVersion = "v1"
      end
      line.call  "    SSD: #{mapping.ssd.displayName} - #{size / 1024**3} GB, #{formatVersion}"
      mapping.nonSsd.map do |md|
        capacity = md.capacity
        size = capacity.block * capacity.blockSize
        line.call "    MD: #{md.displayName} - #{size / 1024**3} GB, #{formatVersion}"
      end
    end
  end
  line.call "FaultDomainInfo:"
  if product.version >= '6.0.0' && config.faultDomainInfo && config.faultDomainInfo.name != ""
    line.call "  #{config.faultDomainInfo.name}"
  else
    line.call "  Not configured"
  end
  line.call "NetworkInfo:"
  if config.networkInfo.port.length == 0
    line.call  "  Not configured"
  end
  vmknics = host_data['vmknics']
  config.networkInfo.port.each do |port|
    dev = port.device
    vmknic = vmknics.find{|x| x.device == dev}
    ip = "IP unknown"
    if vmknic
      ip = vmknic.spec.ip.ipAddress
      if ip.nil? || ip.empty?
        ip = []
        ipv6s = vmknic.spec.ip.ipV6Config.ipV6Address
        ipv6s.each do |ipv6|
          if !ipv6.ipAddress.nil? && !ipv6.ipAddress.empty?
            ipv6Start = ipv6.ipAddress.split(':')[0].to_i(16)
            if !(0xfe80 <= ipv6Start && ipv6Start < 0xfec0)
              ip.push(ipv6.ipAddress)
            end
          end
        end
      end
    end
    line.call "  Adapter: #{dev} (#{ip})"
  end
  return info
end


opts :cluster_set_default_policy do
  summary "Set default policy on a cluster"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource
  arg :policy, nil, :type => :string
end

def cluster_set_default_policy cluster, policy
  hosts = cluster.host
  conn = cluster._connection
  pc = conn.propertyCollector
  _run_with_rev(conn, "dev") do
    vsan, = hosts.first.collect 'configManager.vsanSystem'
    cluster_uuid, = vsan.collect 'config.clusterInfo.uuid'

    hosts.map do |host|
      Thread.new do
        c1 = conn.spawn_additional_connection
        host2 = host.dup_on_conn(c1)
        policy_node = host2.esxcli.vsan.policy
        ['cluster', 'vdisk', 'vmnamespace', 'vmswap'].each do |policy_class|
          policy_node.setdefault(
            :clusteruuid => cluster_uuid,
            :policy => policy,
            :policyclass => policy_class,
          )
        end
      end
    end.each{|t| t.join}
  end
end

def _components_in_dom_config dom_config
  VsanHelperMethods._components_in_dom_config dom_config
end

def _compute_vm_to_obj_map vms, vms_props, all_obj_uuids
  VsanHelperMethods._compute_vm_to_obj_map vms, vms_props, all_obj_uuids
end

def _get_vm_obj_uuids vm, vmsProps
  VsanHelperMethods._get_vm_obj_uuids vm, vmsProps
end

class VsanHelperMethods
  def self._components_in_dom_config dom_config
    out = []
    if ['Component', 'Witness'].member?(dom_config['type'])
      out << dom_config
    else
      dom_config.select{|k,v| k =~ /child-\d+/}.each do |k, v|
        out += _components_in_dom_config v
      end
    end
    out
  end

  def self._compute_vm_to_obj_map vms, vms_props, all_obj_uuids
    all_vm_obj_uuids = []
    vmToObjMap = {}
    vms.each do |vm|
      vm_obj_uuids = _get_vm_obj_uuids(vm, vms_props)
      vm_obj_uuids = vm_obj_uuids.select{|x, v| all_obj_uuids.member?(x)}
      vm_obj_uuids = vm_obj_uuids.reject{|x, v| all_vm_obj_uuids.member?(x)}
      all_vm_obj_uuids += vm_obj_uuids.keys
      if vm_obj_uuids.length > 0
        vmToObjMap[vm] = vm_obj_uuids
      end
    end
    vmToObjMap
  end

  def self._get_vm_obj_uuids vm, vmsProps
    obj_uuids = {}
    devices = vmsProps[vm]['config.hardware.device'] || []
    disks = vmsProps[vm]['disks'] = devices.select{|x| x.is_a?(VIM::VirtualDisk)}
    pathName = vmsProps[vm]['summary.config'].vmPathName
    namespaceUuid = vmsProps[vm]['namespaceUuid'] =
      pathName.split("] ")[1].split("/")[0]
    obj_uuids[namespaceUuid] = pathName
    disks.each do |disk|
      backing = disk.backing
      while backing
        obj_uuids[backing.backingObjectId] = backing.fileName
        backing = backing.parent
      end
    end
    layoutEx = []
    layoutEx = vmsProps[vm]['layoutEx.file'] if !vmsProps[vm]['layoutEx.file'].nil?
    layoutEx.each do |l|
      obj_uuids[l.props[:backingObjectId]] = l.props[:name] if !l.props[:backingObjectId].nil?
    end
    obj_uuids
  end
end

def _normalize_uuid uuid
  uuid = uuid.gsub("-", "")
  uuid = "%s-%s-%s-%s-%s" % [
    uuid[0..7], uuid[8..11], uuid[12..15],
    uuid[16..19], uuid[20..31]
  ]
  uuid
end

def _print_dom_config_tree_int dom_config, dom_components_str, indent = 0
  pre = "  " * indent
  type = dom_config['type']
  children = dom_config.select{|k,v| k =~ /child-\d+/}
  children = children.sort_by{|k,v| k.gsub("child-", "").to_i}
  children = children.map{|x| x[1]}
  if ['RAID_0', 'RAID_1', 'RAID_5', 'RAID_6', 'Concatenation'].member?(type)
    puts "#{pre}#{type}"
    children.each do |child|
      _print_dom_config_tree_int child, dom_components_str, indent + 1
    end
  elsif ['Configuration'].member?(type)
#    puts "#{pre}#{type}"
    children.each do |child|
      _print_dom_config_tree_int child, dom_components_str, indent + 1
    end
  elsif ['Witness', 'Component'].member?(type)
    comp_uuid = dom_config['componentUuid']
    info = dom_components_str[comp_uuid]
    line = "#{pre}#{type}: #{info[0]}"
    if info[2].length > 0
      puts "#{line} (#{info[1]},"
      puts "#{' ' * line.length}  #{info[2]})"
    else
      puts "#{line} (#{info[1]})"
    end
  end
end

def _print_dom_config_tree dom_obj_uuid, obj_infos, indent = 0, opts = {}
  pre = "  " * indent
  dom_obj_infos = obj_infos['dom_objects'][dom_obj_uuid]
  if !dom_obj_infos
    puts "#{pre}Couldn't find info about DOM object '#{dom_obj_uuid}'"
    return
  end
  dom_obj = dom_obj_infos['config']
  policy = dom_obj_infos['policy']

  dom_components = _components_in_dom_config(dom_obj['content'])
  csn = nil
  begin
    csn = dom_obj['content']['attributes']['CSN']
  rescue
  end

  dom_components_str = Hash[dom_components.map do |dom_comp|
    attr = dom_comp['attributes']
    state = attr['componentState']
    comp_uuid = dom_comp['componentUuid']
    state_names = {
      '0' => 'FIRST',
      '1' => 'NONE',
      '2' => 'NEED_CONFIG',
      '3' => 'INITIALIZE',
      '4' => 'INITIALIZED',
      '5' => 'ACTIVE',
      '6' => 'ABSENT',
      '7' => 'STALE',
      '8' => 'RESYNCHING',
      '9' => 'DEGRADED',
      '10' => 'RECONFIGURING',
      '11' => 'CLEANUP',
      '12' => 'TRANSIENT',
      '13' => 'LAST',
    }
    state_name = state.to_s
    if state_names[state.to_s]
      state_name = "#{state_names[state.to_s]} (#{state})"
    end
    props = {
      'state' => state_name,
    }

    if [6, 9].member?(state.to_s.to_i) && attr['staleCsn']
      if attr['staleCsn'] != csn
        props['csn'] = "STALE (#{attr['staleCsn']}!=#{csn})"
      end
    end

    if state.to_s.to_i == 5 && attr['flags'] && (attr['flags'] & (1 << 3) != 0)
       props['csn'] = "STALE (owner stale)"
    end

    comp_policy = {}
    ['readOPS', 'writeOPS'].select{|x| attr[x]}.each do |x|
      comp_policy[x] = attr[x]
    end
    if attr['readCacheReservation'] && attr['readCacheHitRate']
      comp_policy['rc size/hitrate'] = "%.2fGB/%d%%" % [
        attr['readCacheReservation'].to_f / 1024**3,
        attr['readCacheHitRate'],
      ]
    end
    if attr['bytesToSync'] && attr['bytesToSync'] != 0
      comp_policy['dataToSync'] = "%.2f GB" % [
        attr['bytesToSync'].to_f / 1024**3
      ]
    end

    lsom_object = obj_infos['lsom_objects'][comp_uuid]

    md_uuid = dom_comp['diskUuid']
    disk_object = obj_infos['disk_objects'][md_uuid]
    md = obj_infos['vsan_disk_uuids'][md_uuid]

    owner = nil
    if lsom_object
      owner = lsom_object['owner']
    elsif disk_object
      owner = disk_object['owner']
    end

    host = nil
    if owner
      host = obj_infos['host_vsan_uuids'][owner]
    end

    if host
      hostName = obj_infos['host_props'][host]['name']
    else
      hostName = owner
    end

    ssd_uuid = "Unknown"
    ssd = nil
    if !obj_infos['disk_objects'][md_uuid].nil?
      ssd_uuid = obj_infos['disk_objects'][md_uuid]['content']['ssdUuid']
      ssd = obj_infos['vsan_disk_uuids'][ssd_uuid]
    end

    props.merge!({
      'host' => hostName || "Unknown",
      'md' => md ? md.DisplayName : md_uuid,
      'ssd' => ssd ? ssd.DisplayName : ssd_uuid,
    })
    if !lsom_object
      props['note'] = 'LSOM object not found'
    end

    if !attr['nVotes'] || attr['nVotes'] == 0
      attr['nVotes'] = 1
    end
    comp_policy['votes'] = attr['nVotes']
    if lsom_object && lsom_object['content']['capacityUsed']
      physUsed = lsom_object['content']['capacityUsed'] / 1024.0**3
      comp_policy['usage'] = "%.1f GB" % physUsed
    end
    if opts[:include_detailed_usage]
      if lsom_object && lsom_object['content']['physCapacityUsed']
        physUsed = lsom_object['content']['physCapacityUsed'] / 1024.0**3
        comp_policy['physUsage'] = "%.1f GB" % physUsed
      end
    end
    if opts[:highlight_disk] && md_uuid == opts[:highlight_disk]
      props['md'] = "**#{props['md']}**"
    elsif opts[:highlight_disk] && ssd_uuid == opts[:highlight_disk]
      props['ssd'] = "**#{props['ssd']}**"
    end
    propsStr = props.map{|k,v| "#{k}: #{v}"}.join(", ")
    comp_policy_str = comp_policy.map{|k,v| "#{k}: #{v}"}.join(", ")
    [comp_uuid, [comp_uuid, propsStr, comp_policy_str]]
  end]

  if policy
    policy = policy.map{|k,v| "#{k} = #{v}"}.join(", ")
  else
    policy = "No POLICY entry found in CMMDS"
  end
  owner = obj_infos['host_vsan_uuids'][dom_obj['owner']]
  if owner
    owner = obj_infos['host_props'][owner]['name']
  else
    owner = "unknown"
  end

  objVersion = 1
  if dom_obj['content']['attributes']['objectVersion']
    objVersion = dom_obj['content']['attributes']['objectVersion']
    objVersion = _marshal_vsan_version(objVersion)
  end
  attrStr = "v#{objVersion}, owner: #{owner}, policy: #{policy}"
  puts "#{pre}DOM Object: #{dom_obj['uuid']} (#{attrStr})"
  if opts[:context]
    puts "#{pre}  Context: #{opts[:context]}"
  end
  _print_dom_config_tree_int dom_obj['content'], dom_components_str, indent
end

def _vsan_host_disks_info hosts
  VsanHelperMethods._vsan_host_disks_info hosts
end

# hosts is a hash: host => hostname
class VsanHelperMethods
def self._vsan_host_disks_info hosts
  hosts.each do |k,v|
    if !v
      hosts[k] = k.name
    end
  end

  conn = hosts.keys.first._connection
  vsanDiskUuids = {}
  $disksCache ||= {}
  if !hosts.keys.all?{|x| $disksCache[x]}
    lock = Mutex.new
    hosts.map do |host, hostname|
      Thread.new do
        if !$disksCache[host]
          c1 = conn.spawn_additional_connection
          host2 = host.dup_on_conn(c1)
          $disksCache[host] = []
          lock.synchronize do
            puts "#{Time.now}: Fetching VSAN disk info from #{hostname} (may take a moment) ..."
          end
          begin
            Timeout.timeout(45) do
              list = host2.esxcli.vsan.storage.list
              list.each{|x| x._set_property :host, host}
              $disksCache[host] = list
            end
          rescue Exception => ex
            lock.synchronize do
              puts "#{Time.now}: Failed to gather from #{hostname}: #{ex.class}: #{ex.message}"
            end
          end
        end
      end
    end.each{|t| t.join}
    puts "#{Time.now}: Done fetching VSAN disk infos"
  end
  hosts.map do |host, hostname|
    disks = $disksCache[host]
    disks.each do |disk|
      vsanDiskUuids[disk.VSANUUID] = disk
    end
  end

  vsanDiskUuids
end
end


def _vsan_cluster_disks_info cluster_or_host, opts = {}
  pc = cluster_or_host._connection.propertyCollector
  model = VsanModel.new([cluster_or_host])
  if opts[:hosts_props]
    hosts_props = opts[:hosts_props]
  else
    hosts_props = model.basic['hosts_props']
  end
  hosts_props = hosts_props.select do |k,v|
    v['runtime.connectionState'] == 'connected'
  end
  vsan_systems = hosts_props.map{|h,p| p['configManager.vsanSystem']}
  vsan_props = pc.collectMultiple(vsan_systems, 'config.clusterInfo')
  host_vsan_uuids = Hash[hosts_props.map do |host, props|
    vsan_system = props['configManager.vsanSystem']
    vsan_info = vsan_props[vsan_system]['config.clusterInfo']
    [vsan_info.nodeUuid, host]
  end]
  vsan_disk_uuids = {}
  vsan_disk_uuids.merge!(
    _vsan_host_disks_info(Hash[hosts_props.map{|h, p| [h, p['name']]}])
  )

  [host_vsan_uuids, hosts_props, vsan_disk_uuids]
end

opts :object_info do
  summary "Fetch information about a VSAN object"
  arg :cluster, "Cluster on which to fetch the object info", :lookup => [VIM::HostSystem, VIM::ClusterComputeResource]
  arg :obj_uuid, nil, :type => :string, :multi => true
  opt :skip_ext_attr, "Don't fetch extended attributes", :type => :boolean
  opt :include_detailed_usage, "Include detailed usage info", :type => :boolean
end

def object_info cluster, obj_uuids, opts = {}
  opts[:cluster] = cluster
  objs = _object_info(obj_uuids, opts.merge(
    :get_ext_attrs => !opts[:skip_ext_attr]
  ))
  indent = 0
  obj_uuids.each do |obj_uuid|
    _print_dom_config_tree(
      obj_uuid, objs, indent,
      :include_detailed_usage => opts[:include_detailed_usage]
    )
    if objs['extattrs'] && objs['extattrs'][obj_uuid]
      extattr = objs['extattrs'][obj_uuid]
      if extattr['Object size']
        size = extattr['Object size']
        puts "  Extended attributes:"
        puts "    Address space: %dB (%.2f GB)" % [size, size.to_f / 1024**3]
        puts "    Object class: %s" % extattr['Object class']
        puts "    Object path: %s" % extattr['Object path']
        puts "    Object capabilities: %s" % extattr['Object capabilities']
      end
    end
    puts ""
  end
end

opts :disk_object_info do
  summary "Fetch information about all VSAN objects on a given physical disk"
  arg :cluster_or_host, "Cluster or host on which to fetch the object info", :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  arg :disk_uuid, nil, :type => :string, :multi => true
end

def disk_object_info cluster_or_host, disk_uuids, opts = {}
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  _run_with_rev(conn, "dev") do
    # XXX: This doesn't yet work when no cluster is given
    host_vsan_uuids, hosts_props, vsan_disk_uuids = _vsan_cluster_disks_info(cluster_or_host)

    input_disk_uuids = []
    m_disk_uuids = []
    disk_uuids.each do |disk_uuid|
      disk_matchingDisplayname = vsan_disk_uuids.find {|k,v| v.DisplayName == disk_uuid}
      disk_matchingUuid = vsan_disk_uuids.find {|k,v| k == disk_uuid}
      if disk_matchingDisplayname
        if cluster_or_host.is_a?(VIM::HostSystem)
          input_disk_uuids << disk_matchingDisplayname
          # The disk information was retrieved through esxcli.vsan.storage.list
          # which will show all capacity flash as SSD, so for a SSD, we must
          # whether it is used as capacity tier, to figure out whether it is
          # a cache SSD.
          if disk_matchingDisplayname[1].IsSSD && !disk_matchingDisplayname[1].IsCapacityTier
            disks = vsan_disk_uuids.find_all do |k,v|
              v.VSANDiskGroupName == disk_uuid unless v.DisplayName == disk_uuid
            end
            m_disk_uuids += disks
          else
            m_disk_uuids << disk_matchingDisplayname
          end
        else
          err "Disk displayName can be used only if first argument is host"
        end
      elsif disk_matchingUuid
        input_disk_uuids << disk_matchingUuid
        if disk_matchingUuid[1].IsSSD && !disk_matchingUuid[1].IsCapacityTier
          disks = vsan_disk_uuids.find_all do |k,v|
            v.VSANDiskGroupUUID == disk_uuid unless k == disk_uuid
          end
          m_disk_uuids += disks
        else
          m_disk_uuids << disk_matchingUuid
        end
      else
        input_disk_uuids << [disk_uuid]
        m_disk_uuids << [disk_uuid]
      end
    end
    input_disk_uuids.map! {|x| x[0]}
    m_disk_uuids.map! {|x| x[0]}

    model = VsanModel.new([cluster_or_host])
    hosts = model.basic['vsan_enabled_hosts']

    if hosts.length == 0
      err "Couldn't find any vsan enabled hosts"
    end

    dslist = hosts.first.datastore
    dslist_props = pc.collectMultiple(dslist, 'name', 'summary.type')
    vsandslist = dslist_props.select{|k, v| v['summary.type'] == 'vsan'}.keys
    vsands = vsandslist.first
    if !vsands
      err "Couldn't find VSAN datastore"
    end
    vms = vsands.vm
    vms_props = pc.collectMultiple(vms,
      'name', 'config.hardware.device',
      'summary.config'
    )
    objects = {}
    vms.each do |vm|
      disks = vms_props[vm]['disks'] =
        vms_props[vm]['config.hardware.device'].select{|x| x.is_a?(VIM::VirtualDisk)}
      namespaceUuid = vms_props[vm]['namespaceUuid'] =
        vms_props[vm]['summary.config'].vmPathName.split("] ")[1].split("/")[0]

      objects[namespaceUuid] = [vm, :namespace]
      disks.each do |disk|
        backing = disk.backing
        while backing
          objects[backing.backingObjectId] = [vm, backing.fileName]
          backing = backing.parent
        end
      end
    end

    vsanIntSys = hosts_props[hosts.first]['configManager.vsanInternalSystem']
    json = vsanIntSys.QueryObjectsOnPhysicalVsanDisk(:disks => m_disk_uuids)
    if json == "BAD"
      err "Server rejected VSAN object-on-disk query"
    end
    result = nil
    begin
      result = rvc_load_json(json)
    rescue
      err "Server failed to query VSAN objects-on-disk: #{json}"
    end

    result.merge!({
      'host_vsan_uuids' => host_vsan_uuids,
      'host_props' => hosts_props,
      'vsan_disk_uuids' => vsan_disk_uuids,
    })

    input_disk_uuids.each do |disk_uuid|
      dom_obj_uuids = []
      disk_info = vsan_disk_uuids[disk_uuid]
      if disk_info
        name = "#{disk_info.DisplayName} (#{disk_uuid})"
        if disk_info.IsSSD && !disk_info.IsCapacityTier
          m_disks = vsan_disk_uuids.find_all do
            |k, v| v.VSANDiskGroupUUID == disk_uuid unless (v.IsSSD && !v.IsCapacityTier)
          end
          m_disks ? m_disks.map!{|x| x[0]} : disk_uuid
          m_disks.each {|m_disk| dom_obj_uuids += result['objects_on_disks'][m_disk]}
        else
          dom_obj_uuids = result['objects_on_disks'][disk_uuid]
        end
      else
        name = disk_uuid
      end
      puts "Physical disk #{name}:"
      indent = 1
      dom_obj_uuids.each do |obj_uuid|
        object = objects[obj_uuid]
        if object && object[1] == :namespace
          vm_name = vms_props[object[0]]['name']
          context = "Part of VM #{vm_name}: Namespace directory"
        elsif object
          vm_name = vms_props[object[0]]['name']
          context = "Part of VM #{vm_name}: Disk: #{object[1]}"
        else
          context = "Can't attribute object to any VM, may be swap?"
        end
        _print_dom_config_tree(
          obj_uuid, result, indent,
          :highlight_disk => disk_uuid,
          :context => context
        )
      end
      puts ""
    end
  end
end


opts :cmmds_find do
  summary "CMMDS Find"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :type, "CMMDS type, e.g. DOM_OBJECT, LSOM_OBJECT, POLICY, DISK etc.", :type => :string, :short => 't'
  opt :uuid, "UUID of the entry.", :type => :string, :short => 'u'
  opt :owner, "UUID of the owning node.", :type => :string, :short => 'o'
end

def cmmds_find cluster_or_host, opts
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  entries = []
  hostUuidMap = {}

  _run_with_rev(conn, "dev") do
    vsanIntSys = nil
    model = VsanModel.new([cluster_or_host])
    connected_hosts = model.basic['connected_hosts']
    hosts_props = model.basic['hosts_props']
    host = connected_hosts.first
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
    vsanSysList = Hash[hosts_props.map do |host, props|
      [props['name'], props['configManager.vsanSystem']]
    end]
    clusterInfos = pc.collectMultiple(vsanSysList.values,
                                      'config.clusterInfo')
    hostUuidMap = Hash[vsanSysList.map do |hostname, sys|
      [clusterInfos[sys]['config.clusterInfo'].nodeUuid, hostname]
    end]
    entries = vsanIntSys.query_cmmds([{
      :owner => opts[:owner],
      :uuid => opts[:uuid],
      :type => opts[:type],
    }])
  end

  t = Terminal::Table.new()
  t << ['#', 'Type', 'UUID', 'Owner', 'Health', 'Content']
  t.add_separator
  entries.each_with_index do |entry, i|
    entry['content']['formatVersion'] =
      _marshal_vsan_version(entry['content']['formatVersion'])
    t << [
      i + 1,
      entry['type'],
      entry['uuid'],
      hostUuidMap[entry['owner']] || entry['owner'],
      entry['health'],
      PP.pp(entry['content'], ''),
    ]
  end

  puts t
end


def convert_uuids uuids
  nUuids = {}
  uuids.each do |uuid|
    begin
      oUuid = uuid.split(' ').join()
      nUuids[oUuid[0..7] + '-' + oUuid[8..11] + '-' +
             oUuid[12..20] + '-' + oUuid[21..-1]] = true
    rescue Exception => ex
      puts "Ignoring malformed uuid #{uuid}: #{ex.class}: #{ex.message}"
    end
  end

  return nUuids
end

# It is possible for the management stack (hostd and vc) to lose the handle of
# a VM which is powered on (has a running vmx instance). No further operations
# can be performed on the VM because the running vmx holds locks on the VM.
# This API is intended to find such VMs. We look for VMs who's power state
# is not poweredOn (poweredOff, unknown, etc) for which there is a running vmx
# instance on any host in the cluster.

def find_inconsistent_vms cluster_or_host

  # Find all non-poweredon vms.
  conn = cluster_or_host._connection
  pc = conn.propertyCollector
  model = VsanModel.new([cluster_or_host])
  hosts = model.basic['hosts']
  vms = pc.collectMultiple(hosts, 'vm').values.map{|x| x['vm']}.flatten
  vmProps = pc.collectMultiple(vms, 'name', 'runtime.powerState',
                               'summary.config.uuid')
  notOnVMs = vmProps.select{|vm, p| p['runtime.powerState'] !=
                                    'poweredOn'}.keys
  # Get list of all running vms on all hosts in parallel.
  threads = []
  processList = {}
  hosts.each do |host|
    threads << Thread.new do
      begin
        processList[host] = host.esxcli.vm.process.list
      rescue Exception => ex
        puts "Error getting vm process list on #{host.name}: " \
             "#{ex.class}: #{ex.message}"
      end
    end
  end
  threads.each{|t| t.join}
  original_uuids = []
  processList.values.flatten.each do |process|
    if process.UUID
      original_uuids << process.UUID
    else
      puts "No UUID known for VM #{process.DisplayName}, can't perform checking"
    end
  end
  uuids = convert_uuids(original_uuids)

  inconsistentVMs = notOnVMs.select{|vm|
                                    uuids.has_key?(vmProps[vm]['summary.config.uuid'])}
  if not inconsistentVMs.empty?
    puts "Found VMs for which VC/hostd/vmx are out of sync:"
    inconsistentVMs.each do |vm|
      puts "#{vmProps[vm]['name']}"
    end
  else
    puts "Did not find VMs for which VC/hostd/vmx are out of sync"
  end

  return inconsistentVMs
end

def fix_inconsistent_vms vms
  begin
    tasks = []
    vms.each do |vm|
      begin
        path = vm.summary.config.vmPathName
        rp = vm.resourcePool
        folder = vm.parent
        name = vm.name
        host = vm.summary.runtime.host
        puts("Unregistering VM #{name}")
        vm.UnregisterVM()
        puts("Registering VM #{name}")
        tasks << folder.RegisterVM_Task(:path => path,
                                        :name => name,
                                        :asTemplate => false,
                                        :pool => rp,
                                        :host => host)
      rescue Exception => ex
        puts "Skipping VM #{name} due to exception: " \
             "#{ex.class}: #{ex.message}"
      end
    end
    progress(tasks)
  end
end

opts :fix_renamed_vms do
   summary "This command can be used to rename some VMs which get renamed " \
           "by the VC in case of storage inaccessibility. It is "           \
           "possible for some VMs to get renamed to vmx file path. "        \
           "eg. \"/vmfs/volumes/vsanDatastore/foo/foo.vmx\". This command " \
           "will rename this VM to \"foo\". This is the best we can do. "   \
           "This VM may have been named something else but we have no way " \
           "to know. In this best effort command, we simply rename it to "  \
           "the name of its config file (without the full path and .vmx "   \
           "extension ofcourse!)."
   arg :vms, nil, :lookup => VIM::VirtualMachine, :multi => true
   opt :force, "Force to fix name", :type => :boolean
end

def fix_renamed_vms vms, opts
   begin
      conn = vms.first._connection
      pc = conn.propertyCollector
      vmProps = pc.collectMultiple(vms, 'name', 'summary.config.vmPathName')

      rename = {}
      puts "Continuing this command will rename the following VMs:"
      begin
         vmProps.each do |k,v|
            name = v['name']
            cfgPath = v['summary.config.vmPathName']
            if /.*vmfs.*volumes.*/.match(name)
               m = /.+\/(.+)\.vmx/.match(cfgPath)
               if name != m[1]
                  # Save it in a hash so we don't have to do it again if
                  # user choses Y.
                  rename[k] = m[1]
                  puts "#{name} -> #{m[1]}"
               end
            end
         end
      rescue Exception => ex
         # Swallow the exception. No need to stop other vms.
         puts "Skipping VM due to exception: #{ex.class}: #{ex.message}"
      end

      if rename.length == 0
         puts "Nothing to do"
         return
      end

      proceed = opts[:force] || _questionnaire(
        "Do you want to continue [Y/N]?",
        ['y', 'n'],
        'y'
      )
      if proceed
         puts "Renaming..."
         tasks = rename.keys.map do |vm|
            vm.Rename_Task(:newName => rename[vm])
         end
         progress(tasks)
      end
   end
end

opts :vm_object_info do
  summary "Fetch VSAN object information about a VM"
  arg :vms, nil, :lookup => VIM::VirtualMachine, :multi => true
  opt :cluster, "Cluster on which to fetch the object info", :lookup => VIM::ClusterComputeResource
  opt :perspective_from_host, "Host to query object info from", :lookup => VIM::HostSystem
  opt :include_detailed_usage, "Include detailed usage info", :type => :boolean
end

def vm_object_info vms, opts
  begin
    conn = vms.first._connection
    pc = conn.propertyCollector
    firstVm = vms.first
    host = firstVm.runtime.host
    if !host
      puts "VM #{firstVm.name} doesn't have an assigned host (yet?)"
      puts "VM #{firstVM.name} isn't ready for use"
      return
    end
    opts[:cluster] ||= host.parent
    _run_with_rev(conn, "dev") do
      vmsProps = pc.collectMultiple(vms,
        'name', 'config.hardware.device', 'summary.config',
        'runtime.host', 'layoutEx.file',
      )
      obj_uuids = []
      objToHostMap = {}
      vms.each do |vm|
        vm_obj_uuids = _get_vm_obj_uuids(vm, vmsProps).keys
        vm_obj_uuids.each{|x| objToHostMap[x] = vmsProps[vm]['runtime.host']}
        obj_uuids += vm_obj_uuids
      end
      opts[:objToHostMap] = objToHostMap

      objs = _object_info(obj_uuids, opts)
      hosts_props = objs['host_props']

      vms.each do |vm|
        vmProps = vmsProps[vm]
        disks = vmProps['disks']
        puts "VM #{vmProps['name']}:"
        if objs['has_partitions']
          vmHost = vmProps['runtime.host']
          puts "  VM registered on host: #{hosts_props[vmHost]['name']}"
        end

        indent = 1
        pre = "  " * indent
        puts "#{pre}Namespace directory"
        obj_uuid = vmsProps[vm]['namespaceUuid']
        if objs['has_partitions'] && objs['obj_uuid_from_host'][obj_uuid]
          objHost = objs['obj_uuid_from_host'][obj_uuid]
          puts "#{pre}  Shown from perspective of host #{hosts_props[objHost]['name']}"
        end
        _print_dom_config_tree(
          obj_uuid, objs, indent + 1,
          :include_detailed_usage => opts[:include_detailed_usage]
        )

        disks.each do |disk|
          indent = 1
          backing = disk.backing
          while backing
            pre = "  " * indent
            puts "#{pre}Disk backing: #{backing.fileName}"
            obj_uuid = backing.backingObjectId
            if objs['has_partitions'] && objs['obj_uuid_from_host'][obj_uuid]
              objHost = objs['obj_uuid_from_host'][obj_uuid]
              puts "#{pre}  Shown from perspective of host #{hosts_props[objHost]['name']}"
            end
            _print_dom_config_tree(
              obj_uuid, objs, indent + 1,
              :include_detailed_usage => opts[:include_detailed_usage]
            )

            backing = backing.parent
            indent += 1
          end
        end
      end
    end
  rescue Exception => ex
    puts ex.message
    puts ex.backtrace
    raise
  end
end

def _object_info obj_uuids, opts
  if !opts[:cluster]
    err "Must specify a VSAN Cluster"
  end
  host = opts[:host]
  if opts[:cluster].is_a?(VIM::HostSystem)
    host = opts[:cluster]
  end

  model = VsanModel.new([opts[:cluster]])
  # XXX: Verify VSAN is enabled on the cluster
  if host
    hosts = [host]
    conn = host._connection
  else
    hosts = model.basic['hosts']
    conn = opts[:cluster]._connection
  end

  _run_with_rev(conn, "dev") do
    pc = conn.propertyCollector

    hosts_props = pc.collectMultiple(hosts,
      'name', 'runtime.connectionState',
      'configManager.vsanSystem',
      'configManager.vsanInternalSystem'
    )

    hosts = model.basic['vsan_enabled_hosts']
    if hosts.length == 0
      err "Couldn't find any vsan enabled hosts"
    end

    if opts[:perspective_from_host]
      if !connected_hosts.member?(opts[:perspective_from_host])
        err "Perspective-Host not connected, or not in considered group of hosts"
      end
    end

    partitions = model.get_partitions(true) #ignore errors
    partition_exists = (partitions.length > 1)
    if partition_exists
      puts "#{Time.now}: WARNING: VSAN Cluster network partition detected."
      puts "#{Time.now}: The individual partitions of the cluster will have "
      puts "#{Time.now}: different views on object/component availablity. An "
      puts "#{Time.now}: attempt is made to show VM object accessibility from the "
      puts "#{Time.now}: perspective of the host on which a VM is registered. "
      puts "#{Time.now}: Please fix the network partition as soon as possible "
      puts "#{Time.now}: as it will seriously impact the availability of your "
      puts "#{Time.now}: VMs in your VSAN cluster. Check vsan.cluster_info for"
      puts "#{Time.now}: more details."
      puts "#{Time.now}: "
      puts "#{Time.now}: The following partitions were detected:"
      i = 1
      partitions.values.map do |part|
        part_hosts = part.map{|x| hosts_props[x[0]]}.compact.map{|x| x['name']}
        puts "#{Time.now}: #{i}) #{part_hosts.join(", ")}"
        i += 1
      end
      puts ""
      if opts[:perspective_from_host]
        name = hosts_props[opts[:perspective_from_host]]['name']
        puts "Showing data from perspective of host #{name} as requested"
        puts ""
      end
    end

    host_vsan_uuids, host_props, vsan_disk_uuids = _vsan_cluster_disks_info(
      opts[:cluster],
      :hosts_props => hosts_props
    )
    extra_info = {
      'host_vsan_uuids' => host_vsan_uuids,
      'host_props' => host_props,
      'vsan_disk_uuids' => vsan_disk_uuids,
    }

    obj_uuids = obj_uuids.compact.map{|x| _normalize_uuid(x)}
    obj_uuids = obj_uuids.select{|x| is_uuid(x)}

    objs = {'obj_uuid_from_host' => {}}
    objs['has_partitions'] = partition_exists

    # Dealing with partitions:
    # In the non-partitioned case we can just select any host and ask it
    # for the object info, given that CMMDS is (eventual) consistent
    # across the cluster. But during a network partition it is most logical
    # to ask the host on which a VM is registered about what it thinks about
    # the objects in question. So in case of a network partition we fall
    # back to a slower code path that asks each host individually about
    # the objects it (hopefully) knows best about.
    # Note: Upon power on DRS will pick a host to power the VM on. That other
    # host may not be in the same partition and DRS doesn't know about it,
    # so although we tried to show the object from the "right" hosts perspective
    # it may still not be the right host when debugging a power on failure.
    if opts[:objToHostMap] && partition_exists && !opts[:perspective_from_host]
      obj_uuids_groups = obj_uuids.group_by{|x| opts[:objToHostMap][x]}
      obj_uuids_groups.each do |host, group|
        vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
        group_objs = vsanIntSys.query_vsan_objects(:uuids => group)

        # Here we are merging and overriding potentially conflicting
        # information about LSOM_OBJECT and DISK entries. No smarts are
        # applied, as I am not aware of issues arising from those
        # possible inconsistencies.
        group_objs.each do |k,v|
          objs[k] ||= {}
          objs[k].merge!(v)
        end
        group.each do |uuid|
          objs['obj_uuid_from_host'][uuid] = host
        end
      end
    else
      if opts[:perspective_from_host]
        host = opts[:perspective_from_host]
      else
        host = hosts.first
      end
      vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
      objs = vsanIntSys.query_vsan_objects(:uuids => obj_uuids)

      if opts[:get_ext_attrs]
        begin
          objs['extattrs'] = vsanIntSys.query_vsan_obj_extattrs(
            :uuids => obj_uuids
          )
        rescue
          puts "WARNING: Failed to get extended attributes"
        end
      end
    end

    objs.merge!(extra_info)
    objs
  end
end


def _fetch_disk_stats obj, metrics, instances, opts = {}
  conn = obj._connection
  pm = conn.serviceContent.perfManager

  metrics.each do |x|
    err "no such metric #{x}" unless pm.perfcounter_hash.member? x
  end

  interval = pm.provider_summary(obj).refreshRate
  start_time = nil
  if interval == -1
    # Object does not support real time stats
    interval = 300
    start_time = Time.now - 300 * 5
  end
  stat_opts = {
    :interval => interval,
    :startTime => start_time,
    :instance => instances,
    :multi_instance => true,
  }
  stat_opts[:max_samples] = opts[:samples] if opts[:samples]
  res = pm.retrieve_stats [obj], metrics, stat_opts

  out = {}
  if res && res[obj]
    res[obj][:metrics].each do |key, values|
      metric, device = key
      out[device] ||= {}
      out[device][metric] = values
    end
  end
  out
end

opts :vsan_type do
  summary "Show type of VSAN: All-Flash or Hybrid"
  arg :cluster, nil, :lookup => VIM::ComputeResource
end

def vsan_type cluster, 
  host = cluster.host[0]
  begin
    json = host.configManager.vsanInternalSystem.QueryPhysicalVsanDisks(:props => [])
  rescue
    puts "Not VSAN"
    return 
  end
  hash = JSON.parse(json)
  vals = hash.values
  type = "Hybrid"
  vals.each do |val|
    if val["isSsd"] and val["isSsd"] == 1
       if val["isAllFlash"] and val["isAllFlash"] == 1
         type = "All-Flash"
         if val["dedupScope"]
           puts "Dedup_Scope: " + val["dedupScope"].to_s
         end
       end
       break
    end
  end
  puts "VSAN_Type: "+type
end

opts :disks_stats do
  summary "Show stats on all disks in VSAN"
  arg :hosts_and_clusters, nil, :lookup => [VIM::HostSystem, VIM::ClusterComputeResource], :multi => true
end

def disks_stats hosts_and_clusters, opts = {}
  opts[:compute_number_of_components] = true
  conn = hosts_and_clusters.first._connection
  pc = conn.propertyCollector
  _run_with_rev(conn, "dev") do
    model = VsanModel.new(
      hosts_and_clusters,
      [],
      :allow_multiple_clusters => true
    )
    hosts = model.basic['connected_hosts']
    hosts_props = model.basic['hosts_props']

    hosts_vsansys = Hash[hosts_props.map{|k,v| [v['configManager.vsanSystem'], k]}]
    node_uuids = pc.collectMultiple(hosts_vsansys.keys, 'config.clusterInfo.nodeUuid')
    node_uuids = Hash[node_uuids.map do |k, v|
      [v['config.clusterInfo.nodeUuid'], hosts_vsansys[k]]
    end]

    disks = model.get_physical_vsan_disks

    vsan_disks_info = {}
    vsan_disks_info.merge!(
      _vsan_host_disks_info(Hash[hosts.map{|h| [h, hosts_props[h]['name']]}])
    )
    disks.each do |k, v|
      v['esxcli'] = vsan_disks_info[v['uuid']]
      if v['esxcli']
        v['host'] = v['esxcli']._get_property :host
      end
    end

    disks = disks.values.sort_by do |x|
      host_props = hosts_props[x['host']]
      host_props ? host_props['name'] : ''
    end

    t = Terminal::Table.new()
    arr = []
    t << [nil,           nil,     nil,    'Num',  'Capacity', nil,    nil,        'Status']
    t << ['DisplayName', 'Host', 'isSSD', 'Comp', 'Total',    'Used', 'Reserved', 'Health']
    t.add_separator
    # XXX: Would be nice to show displayName and host

    groups = disks.group_by{|x| x['esxcli'] ? x['esxcli'].VSANDiskGroupUUID : nil}

    groups.each do |group, disks|
      disks.sort_by{|x| -x['isSsd']}.each do |x|
        info = x['esxcli']
        host_props = hosts_props[x['host']]

        capacity = x['capacity'].to_f
        if x['isSsd'] == 1
          if x.include?('ssdCapacity')
            capacity = x['ssdCapacity'].to_f
          else
            capacity = capacity * 10 / 7 #calc by the default portion of ssd read cache
          end
        end
        col1 = [(x['isSsd'] == 1) ? 'SSD' : 'MD',"%.2f" % [capacity / 1024**3],]
        cols = [
          info ? info.DisplayName : 'N/A',
          host_props ? host_props['name'] : 'N/A',
          #x['uuid'],
          (x['isSsd'] == 1) ? 'SSD' : 'MD',
          x['lsom_objects_count'] || 'N/A',
          "%.2f GB" % [capacity / 1024**3],
          "%.2f %%" % [x['capacityUsed'].to_f * 100 / capacity],
          "%.2f %%" % [x['capacityReserved'].to_f * 100 / capacity],
        ]

        formatVersion = _marshal_vsan_version(x['formatVersion'])
        cols << "#{x['rvc_health_str']} (v#{formatVersion})"
        t << cols
        arr << col1
      end
      if group != groups.keys.last
        t.add_separator
      end
    end
    count = 0
    md_count = 0
    sum=0
    arr.each do |col|
      if col[0] == "SSD"
        count = count + 1
        sum= sum + col[1].to_i
      end
      if col[0] == "MD"
         md_count = md_count + 1
      end
    end
    puts t
    puts "Total_Cache_Size: "+sum.to_s
    puts "Total_DiskGroup_Number: "+count.to_s
    puts "Total_Capacity_Disk_Number: "+md_count.to_s
  end
end

opts :whatif_host_failures do
  summary "Simulates how host failures impact VSAN resource usage"
  banner <<-EOS

The command shows current VSAN disk usage, but also simulates how
disk usage would evolve under a host failure. Concretely the simulation
assumes that all objects would be brought back to full policy
compliance by bringing up new mirrors of existing data.
The command makes some simplifying assumptions about disk space
balance in the cluster. It is mostly intended to do a rough estimate
if a host failure would drive the cluster to being close to full.

EOS
  arg :hosts_and_clusters, nil, :lookup => [VIM::HostSystem, VIM::ClusterComputeResource], :multi => true
  opt :num_host_failures_to_simulate, "Number of host failures to simulate", :default => 1
  opt :show_current_usage_per_host, "Show current resources used per host"
end

def whatif_host_failures hosts_and_clusters, opts = {}
  opts[:compute_number_of_components] = true
  conn = hosts_and_clusters.first._connection
  hosts = hosts_and_clusters.select{|x| x.is_a?(VIM::HostSystem)}
  pc = conn.propertyCollector
  model = VsanModel.new(
    hosts_and_clusters,
    [],
    :allow_multiple_clusters => true
  )
  hosts += model.basic['hosts']
  hosts = hosts.uniq

  if opts[:num_host_failures_to_simulate] != 1
    err "Only simulation of 1 host failure has been implemented"
  end

  _run_with_rev(conn, "dev") do
    hosts_props = pc.collectMultiple(hosts,
      'name',
      'runtime.connectionState',
      'configManager.vsanSystem',
      'configManager.vsanInternalSystem'
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
    disks = {}
    vsanIntSys = hosts_props[hosts.first]['configManager.vsanInternalSystem']
    disks = vsanIntSys.QueryPhysicalVsanDisks(:props => [
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
    if disks == "BAD"
      err "Server failed to gather VSAN disk info"
    end
    begin
      disks = rvc_load_json(disks)
    rescue
      err "Server didn't provide VSAN disk info: #{objs}"
    end

    hosts.map do |host|
      Thread.new do
        c1 = conn.spawn_additional_connection
        props = hosts_props[host]
        vsanIntSys2 = props['configManager.vsanInternalSystem']
        vsanIntSys3 = vsanIntSys2.dup_on_conn(c1)
        res = vsanIntSys3.query_vsan_statistics(:labels => ['lsom-node'])
        hosts_props[host]['lsom.node'] = res['lsom.node']
      end
    end.each{|t| t.join}

    hosts_disks = Hash[disks.values.group_by{|x| x['owner']}.map do |owner, hostDisks|
      props = {}
      hdds = hostDisks.select{|disk| disk['isSsd'] == 0}
      ssds = hostDisks.select{|disk| disk['isSsd'] == 1}
      hdds.each do |disk|
        [
          'capacityUsed', 'capacityReserved',
          'capacity', 'lsom_objects_count'
        ].each do |x|
          props[x] ||= 0
          props[x] += disk[x]
        end
      end
      ssds.each do |disk|
        [
          'capacityReserved', 'capacity',
        ].each do |x|
          props["ssd_#{x}"] ||= 0
          props["ssd_#{x}"] += disk[x]
        end
      end
      h = node_uuids[owner]
      props['host'] = h
      props['hostname'] = h ? hosts_props[h]['name'] : owner
      props['numHDDs'] = hdds.length
      props['maxComponents'] = 3000
      if hosts_props[h]['lsom.node']
        props['maxComponents'] = hosts_props[h]['lsom.node']['numMaxComponents']
      end
      [owner, props]
    end]

    sorted_hosts = hosts_disks.values.sort_by{|x| -x['capacityUsed']}

    if opts[:show_current_usage_per_host]
      puts "Current utilization of hosts:"
      t = Terminal::Table.new()
      t << [nil,    nil,       'HDD Capacity', nil,    nil,    'Components', 'SSD Capacity']
      t << ['Host', 'NumHDDs', 'Total',    'Used', 'Reserved', 'Used',       'Reserved']
      t.add_separator

      hosts_disks.each do |owner, x|
        cols = [
          x['hostname'],
          x['numHDDs'],
          "%.2f GB" % [x['capacity'].to_f / 1024**3],
          "%.0f %%" % [x['capacityUsed'].to_f * 100 / x['capacity'].to_f],
          "%.0f %%" % [x['capacityReserved'].to_f * 100 / x['capacity'].to_f],
          "%4u/%u (%.0f %%)" % [
            x['lsom_objects_count'],
            x['maxComponents'],
            x['lsom_objects_count'].to_f * 100 / x['maxComponents'].to_f
          ],
          "%.0f %%" % [x['ssd_capacityReserved'].to_f * 100 / x['ssd_capacity'].to_f],
        ]
        t << cols
      end
      puts t
      puts ""
    end

    puts "Simulating #{opts[:num_host_failures_to_simulate]} host failures:"
    puts ""
    worst_host = sorted_hosts[0]

    if sorted_hosts.length < 3
      puts "Cluster unable to regain full policy compliance after host failure, "
      puts "not enough hosts remaining."
      return
    end

    t = Terminal::Table.new()
    t << ["Resource", "Usage right now", "Usage after failure/re-protection"]
    t.add_separator
    capacityRow = ["HDD capacity"]

    # Capacity before failure
    used = sorted_hosts.map{|x| x['capacityUsed']}.sum
    total = sorted_hosts.map{|x| x['capacity']}.sum
    free = total - used
    usedPctOriginal = 100.0 - (free.to_f * 100 / total.to_f)
    capacityRow << "%3.0f%% used (%.2f GB free)" % [
      usedPctOriginal,
      free.to_f / 1024**3,
    ]

    # Capacity after rebuild
    used = sorted_hosts[1..-1].map{|x| x['capacityUsed']}.sum
    total = sorted_hosts[1..-1].map{|x| x['capacity']}.sum
    additional = worst_host['capacityUsed']
    free = total - used
    usedPctBeforeReMirror = 100.0 - (free.to_f * 100 / total.to_f)
    usedPctAfterReMirror = 100.0 - ((free - additional).to_f * 100 / total.to_f)
    usedPctIncrease = usedPctAfterReMirror - usedPctOriginal
    capacityRow << "%3.0f%% used (%.2f GB free)" % [
      usedPctAfterReMirror,
      (free - additional).to_f / 1024**3,
    ]
    t << capacityRow

    # Components before failure
    sorted_hosts = hosts_disks.values.sort_by{|x| -x['lsom_objects_count']}
    worst_host = sorted_hosts[0]
    used = sorted_hosts.map{|x| x['lsom_objects_count']}.sum
    total = sorted_hosts.map{|x| x['maxComponents']}.sum
    free = total - used
    usedPctOriginal = 100.0 - (free.to_f * 100 / total.to_f)
    componentsRow = ["Components"]
    componentsRow << "%3.0f%% used (%u available)" % [
      usedPctOriginal,
      free,
    ]

    # Components after rebuild
    used = sorted_hosts[1..-1].map{|x| x['lsom_objects_count']}.sum
    total = sorted_hosts[1..-1].map{|x| x['maxComponents']}.sum
    additional = worst_host['lsom_objects_count']
    free = total - used
    usedPctBeforeReMirror = 100.0 - (free.to_f * 100 / total.to_f)
    usedPctAfterReMirror = 100.0 - ((free - additional).to_f * 100 / total.to_f)
    usedPctIncrease = usedPctAfterReMirror - usedPctOriginal
    componentsRow << "%3.0f%% used (%u available)" % [
      usedPctAfterReMirror,
      (free - additional),
    ]
    t << componentsRow

    # RC reservations before failure
    sorted_hosts = hosts_disks.values.sort_by{|x| -x['ssd_capacityReserved']}
    worst_host = sorted_hosts[0]
    used = sorted_hosts.map{|x| x['ssd_capacityReserved']}.sum
    total = sorted_hosts.map{|x| x['ssd_capacity']}.sum
    free = total - used
    usedPctOriginal = 100.0 - (free.to_f * 100 / total.to_f)
    rcReservationsRow = ["RC reservations"]
    rcReservationsRow << "%3.0f%% used (%.2f GB free)" % [
      usedPctOriginal,
      free.to_f / 1024**3,
    ]

    # RC reservations after rebuild
    used = sorted_hosts[1..-1].map{|x| x['ssd_capacityReserved']}.sum
    total = sorted_hosts[1..-1].map{|x| x['ssd_capacity']}.sum
    additional = worst_host['ssd_capacityReserved']
    free = total - used
    usedPctBeforeReMirror = 100.0 - (free.to_f * 100 / total.to_f)
    usedPctAfterReMirror = 100.0 - ((free - additional).to_f * 100 / total.to_f)
    usedPctIncrease = usedPctAfterReMirror - usedPctOriginal
    rcReservationsRow << "%3.0f%% used (%.2f GB free)" % [
      usedPctAfterReMirror,
      (free - additional).to_f / 1024**3,
    ]
    t << rcReservationsRow

    puts t
  end
end


def _observe_snapshot host, hosts, vmViews, hosts_props, cmmds_history=false
  startTime = Time.now
  observation = {
    'cmmds' => {
      'clusterInfos' => {},
      'clusterDirs' => {},
    },
    'vsi' => {},
    'inventory' => {},
  }

  observation['inventory']['hosts'] = hosts_props
  observation['inventory']['vms'] = {}

  exceptions = []
  threads = []
  lock = Mutex.new
  begin
  vmViews.values.each do |vmView|
    threads << Thread.new do
      begin
        t1 = Time.now
        c1 = vmView._connection.spawn_additional_connection
        if $rvc_observer_profiling
          c1.profiling = true
        end
        _vmView = vmView.dup_on_conn(c1)
        vms = _vmView.view

        vmProperties = [
          'name', 'runtime.powerState', 'datastore', 'config.annotation',
          'parent', 'resourcePool', 'storage.perDatastoreUsage',
          'summary.config.memorySizeMB', 'summary.config.numCpu',
          'summary.config.vmPathName', 'config.hardware.device',
          'runtime.connectionState', 'layoutEx.file'
        ]
        _pc = c1.serviceContent.propertyCollector
        vmsProps = _pc.collectMultiple(vms, *vmProperties)
        t2 = Time.now
        puts "Query VM properties: %.2f sec (%d VMs)" % [(t2 - t1), vms.length]
        if $rvc_observer_profiling
          profile = c1.profile
          profile.each do |method, calls|
            fields = [:network_latency, :request_emit, :response_parse]
            info = fields.map do |field|
              calls.map{|x| x[field]}.sum
            end
            puts "  Method: %s - net/emit/parse %.2f/%.2f/%.2f sec" % (
              [method] + info)
          end
          c1.profiling = false
        end
        vmsProps.each do |vm, vmProps|
          vmProps['vsan-obj-uuids'] = {}
          devices = vmProps['config.hardware.device'] || []
          disks = devices.select{|x| x.is_a?(VIM::VirtualDisk)}
          disks.each do |disk|
            newBacking = {}
            newDisk = {
              'unitNumber' => disk.unitNumber,
              'controllerKey' => disk.controllerKey,
              'backing' => newBacking,
            }
            backing = disk.backing
            if !backing.is_a?(VIM::VirtualDiskFlatVer2BackingInfo)
              next
            end
            while backing
              uuid = backing.backingObjectId
              if uuid
                vmProps['vsan-obj-uuids'][uuid] = backing.fileName
                newBacking['uuid'] = uuid
              end
              newBacking['fileName'] = backing.fileName
              backing = backing.parent

              if backing
                newBacking['parent'] = {}
                newBacking = newBacking['parent']
              end
            end

            vmProps['disks'] ||= []
            vmProps['disks'] << newDisk
          end
          # Do not add devices to the snapshot as they are too big
          vmProps.delete('config.hardware.device')

          begin
            vmPathName = vmProps['summary.config.vmPathName']
            uuid = vmPathName.split("] ")[1].split("/")[0]
            vmProps['vsan-obj-uuids'][uuid] = vmPathName
          rescue
          end

          lock.synchronize do
            # XXX: Problem: This key is not unique across hostd instances
            # But if we just make it unique, e.g. by adding the host
            # UUID or IP, then the analyzer may not be able to look up
            # the VM. Any solution needs to also update the analyzer
            observation['inventory']['vms'][vm._ref] = vmProps
          end
        end
      rescue RbVmomi::VIM::ManagedObjectNotFound => monf
        puts "Query VM properties failed: ManagedObjectNotFound. Ignoring"
      rescue Exception => ex
        exceptions << ex
      end
    end
  end
  threads << Thread.new do
    begin
      sleep(10)
      hostname = hosts_props[host]['name']
      _vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
      # XXX: Should pick one host per partition
      c1 = host._connection.spawn_additional_connection
      vsanIntSys1 = _vsanIntSys.dup_on_conn(c1)

      t1 = Time.now
      cmmdsEntries = ["HOSTNAME", "NODE", "DISK", "NET_INTERFACE"]
      if cmmds_history
        cmmdsEntries << "DOM_OBJECT"
      end
      res = vsanIntSys1.query_cmmds(
        cmmdsEntries.map{|x| {:type => x}}
      )
      t2 = Time.now
      puts "Query CMMDS from #{hostname}: %.2f sec (json size: %dKB)" % [
        (t2 - t1), JSON.dump(res).length / 1024
      ]
      observation['cmmds']['clusterDirs'][hostname] = res
    rescue Exception => ex
      exceptions << ex
    end
  end
  hosts.each do |host|
    threads << Thread.new do
      begin
        hostname = hosts_props[host]['name']
        vsanIntSys1 = hosts_props[host]['configManager.vsanInternalSystem']
        c1 = vsanIntSys1._connection.spawn_additional_connection
        vsanIntSys1 = vsanIntSys1.dup_on_conn(c1)

        t1 = Time.now
        _res = vsanIntSys1.QueryVsanStatistics(:labels =>
          [
            'dom', 'worldlets', 'plog',
            'dom-objects', 'lsom-node',
            'mem', 'cpus', 'slabs',
          ])
        t2 = Time.now
        _res2 = vsanIntSys1.QueryVsanStatistics(:labels => [
            'lsom', 'vscsi', 'cbrc', 'disks',
            'system-mem', 'pnics', 'tcpip',
            'vsansparse', 'vit'
          ]
        )
        t3 = Time.now
        #puts "#{_res.length / 1024.0**2}MB #{_res2.length / 1024.0**2}MB"
        res = rvc_load_json(_res)
        res2 = rvc_load_json(_res2)
        res.merge!(res2)
        #[:waitTime, :runTime, :overrunTime, :readyTime].each do |key|
        #  puts res["worldlets"][key.to_s]
        #  # stats are in ns, but deltaT is in s, so convert stats to seconds
        #  res["worldlets"].each do |k,v|
        #    puts v[key.to_s]
        #    v[key.to_s] = v[key.to_s] ? v[key.to_s].to_f / 1000**3 : 0
        #  end
        #end
        puts "Query Stats on #{host.name}: %.2f+%.2f sec (on ESX: %.2f, json size: %dKB)" % [
          (t2 - t1), (t3 - t2), res['on-esx-collect-duration'],
          (_res.length + _res2.length) / 1024
        ]
        observation['vsi'][hostname] = res
      rescue Exception => ex
        exceptions << ex
      end
    end
  end
  threads.each{|x| x.join}
  if exceptions.length > 0
    raise exceptions.first
  end
  rescue Interrupt
    threads.each{|t| t.terminate}
  end

  {
    'type' => 'inventory-snapshot',
    'snapshot' => observation,
    'starttime' => startTime.to_f,
    'endtime' => Time.now.to_f,
  }
end

class VsanObserver
  def initialize(tasksAnalyzer, inventoryAnalyzer,
                 vcInfo, hosts_props, historyPath)
    @tasksAnalyzer = tasksAnalyzer
    @inventoryAnalyzer = inventoryAnalyzer
    @vcInfo = vcInfo
    @hosts_props = hosts_props
    @staticFiles = [
      'graphs.html', 'bg_pattern.png', 'vmw_logo_white.png',
      'graphs.js', 'observer.css', 'vm-graph.svg'
     ]
     @historyPath = historyPath
  end

  def _timerangeInfo
    timeranges = {}
    Dir.entries(@historyPath).each do |entry|
      filename = File.join(
        @historyPath, entry, 'jsonstats', 'misc', 'timerange.json'
      )
      if File.exists?(filename)
        timerange = open(filename, 'r'){|io| JSON.load io.read}
        timeranges[entry] = timerange
      end
    end
    timeranges['current'] = @inventoryAnalyzer.dumpTimerange

    overviewLabel = timeranges
    overviewUrl = Hash[timeranges.map do |key, tr|
      url = "/history/#{key}/stats.html"
      if key == 'current'
        url = "/"
      end
      [key, url]
    end]
    return {
      'label'=> timeranges,
      'url'=>overviewUrl,
      'keys'=>timeranges.select{|k,tr| tr['firstTS']}.sort_by{|k,tr| -tr['firstTS']}.map{|x| x[0]}
    }
  end

  def _runERB(filename, b)
    @erbFileContentCache ||= {}
    erbFilename = File.join($analyser_lib_dirname, filename)
    content = open(erbFilename, 'r').read
    @erbFileContentCache[filename] = content
    ERB.new(content).result(b)
  end

  def generate_history_html
    timerangeInfo = _timerangeInfo
    _runERB("history.erb.html", binding)
  end

  def generate_login_html(username, error)
    _runERB("login.erb.html", binding)
  end

  def generate_observer_html
    opts = {}
    refreshString = ""
    vcOS = @vcInfo['about']['osType']
    vcFullName = @vcInfo['about']['fullName']
    testTitleString = "VC #{@vcInfo['hostname']} (#{vcFullName} - #{vcOS})"
    skipTasksTab = true
    graphUpdateMsg = "XXX"
    processed = 0
    puts "#{Time.now}: Generating HTML"
    inventoryAnalyzer = @inventoryAnalyzer
    vcInfo = @vcInfo
    hosts_props = @hosts_props
    tasksAnalyzer = @tasksAnalyzer
    inventoryAnalyzerTabs = @inventoryAnalyzer.generateHtmlTabs(
      true,
      :skipLivenessTab => true,
      :skipLsomExpert => true,
      :skipRdtAsso => true,
    )
    puts "#{Time.now}: Generating HTML (fill in template)"

    if @historyPath
      opts[:timerange] = true
    end

    html = _runERB("stats.erb.html", binding)
    puts "#{Time.now}: HTML length: #{html.length}"

    html
  end

  def generate_observer_files(path)
    FileUtils.mkdir_p path
    puts "#{Time.now}: Writing out HTML dump to #{path} ..."
    cwd = Dir.pwd
    Dir.chdir(path)
    begin
      @inventoryAnalyzer.dump()
      @inventoryAnalyzer.dumpAggregates()
      open(File.join(path, "stats.html"), 'w') do |io|
        io.write(self.generate_observer_html())
      end
      @staticFiles.each do |x|
        FileUtils.cp(File.join($analyser_lib_dirname, x), x)
      end
      FileUtils.cp_r $obsPath + "/externallibs/", path
      puts "#{Time.now}: Done writing HTML dump to #{path}"
    ensure
      Dir.chdir(cwd)
    end
  end

  def generate_observer_bundle(bundlePath)
    require 'rubygems/package'
    tarFilename = File.join(
      bundlePath,
      "vsan-observer-#{Time.now.strftime('%Y-%m-%d.%H-%M-%S')}.tar"
    )
    gzFilename = "%s.gz" % tarFilename

    puts "#{Time.now}: Writing out an HTML bundle to #{gzFilename} ..."
    tar = open(tarFilename, 'wb+')
    Gem::Package::TarWriter.new(tar) do |writer|
      @inventoryAnalyzer.dump(:tar => writer)

      useExternalLibs = Dir.exists?(File.join($analyser_lib_dirname, "externallibs"))
      if useExternalLibs
        extPath = File.join($analyser_lib_dirname, "externallibs")
        writer.mkdir('externallibs', 0777)
        ['css', 'js', 'font'].each do |d|
          writer.mkdir(File.join('externallibs', d), 0777)
          Dir.glob(File.join(extPath, d, '*')).each do |f|
            filenameInTar = File.join('externallibs', d, File.basename(f))
            writer.add_file(filenameInTar, 0644) do |io|
              content = open(f, 'r'){|src| src.read}
              io.write(content)
            end
          end
        end
      end

      writer.add_file('stats.html', 0644) do |io|
        html = self.generate_observer_html()
        if useExternalLibs
          html = html.gsub('="/externallibs/', '="externallibs/')
        end
        io.write(html)
      end

      @staticFiles.each do |filename|
        writer.add_file(filename, 0644) do |io|
          content = open("#{$analyser_lib_dirname}/#{filename}", "r") do |src|
            src.read
          end
          if useExternalLibs && filename =~ /.html$/
            content = content.gsub('="/externallibs/', '="externallibs/')
          end
          io.write(content)
        end
      end
    end
    tar.seek(0)

    gz = Zlib::GzipWriter.new(File.new(gzFilename, 'wb'))
    while (buffer = tar.read(10000))
      gz.write(buffer)
    end
    tar.close
    gz.close
    FileUtils.rm(tarFilename)
    puts "#{Time.now}: Done writing HTML bundle to #{gzFilename}"
    gzFilename
  end
end

require 'webrick'
class WebrickSessionManager
  attr_reader :username

  def initialize(conn, opts = {})
    @sessions = {}
    @conn = conn
    @sessionMgr = conn.serviceContent.sessionManager
    @username = @sessionMgr.currentSession.userName
    @opts = opts
  end

  def generateSessionId
    require 'securerandom'
    SecureRandom.uuid
  end

  def login password
    opts = @conn.instance_variable_get(:@opts)
    opts.merge!({:user => @username, :password => password})
    conn2 = RbVmomi::VIM.connect(opts)
    conn2.close
    id = generateSessionId
    @sessions[id] = {
      'id' => id,
      'lastaccess' => Time.now,
      'inactivityTimeout' => 10 * 60,
    }
    WEBrick::Cookie.new('observerSessionID', id)
  end

  def keepalive id
    if @sessions[id]
      @sessions[id]['lastaccess'] = Time.now
    end
  end

  def expireSessions
    now = Time.now
    @sessions = @sessions.select do |id, s|
      s['lastaccess'] + s['inactivityTimeout'] > now
    end
    nil
  end

  def logout(req)
    id = isAliveByReq?(req)
    if !id
      return false
    end
    @sessions.delete(id)
  end

  def isAlive? id
    expireSessions
    if @sessions[id]
      return true
    end
    return false
  end

  def isAliveByReq? req
    cookie = req.cookies.find { |c| c.name == 'observerSessionID' }
    if !cookie
      return false
    end
    if isAlive?(cookie.value)
      keepalive(cookie.value)
      return cookie.value
    end
    return false
  end

  def filterRequest req, res = nil
    if @opts[:noLogin]
      return
    end
    if !isAliveByReq?(req)
      if res
        res.set_redirect(WEBrick::HTTPStatus::TemporaryRedirect, "/login.html")
      end
      raise WEBrick::HTTPStatus::BadRequest
    end
  end

end


class ObserverHistorySpaceManager
  def initialize(tasksAnalyzer, inventoryAnalyzer,
                 vcInfo, hosts_props,
                 opts ={})
    @tasksAnalyzer = tasksAnalyzer
    @inventoryAnalyzer = inventoryAnalyzer
    @vcInfo = vcInfo
    @hosts_props = hosts_props
    @historyPath = opts[:historyPath]
    @observerObj = VsanObserver.new(
      @tasksAnalyzer, @inventoryAnalyzer, @vcInfo, @hosts_props,
      @historyPath
    )
  end

  def directory_size(path)
    path << '/' unless path.end_with?('/')
    if !File.directory?(path)
      return 0
    end

    total_size = 0
    Dir["#{path}**/*"].each do |f|
      total_size += File.size(f) if File.file?(f) && File.size?(f)
    end
    total_size
  end

  def getTimerangeToBeDeleted ranges, maxConsumption
    ranges = ranges.select{|k,tr| k != 'current'}
    ranges.each do |key, tr|
      path = File.join(@historyPath, key)
      bytes = directory_size(path)
      path2 = File.join(@historyPath, "#{key}-observer")
      bytes2 = directory_size(path2)
      tr['jsonBytes'] = bytes2
      tr['htmlBytes'] = bytes
    end
    ranges = Hash[ranges.sort_by do |key, tr|
      tr['firstTS']
    end]

    out = {}

    totalBytesProc = Proc.new do |r|
      r.values.map do |x|
        x['jsonBytes'] + x['htmlBytes']
      end.inject(0, :+)
    end
    out['prevBytes'] = totalBytesProc.call(ranges)
    toBeDeleted = []
    while totalBytesProc.call(ranges) > 100 * maxConsumption
      key = ranges.keys.first
      toBeDeleted[key] = ranges[key]
      ranges.delete(key)
    end
    pp toBeDeleted
    out['delete'] = toBeDeleted
    out['afterBytes'] = totalBytesProc.call(ranges)
    return out
  end

  def deleteOldTimeranges maxConsumption
    ranges = @observerObj._timerangeInfo()['label']
    res = getTimerangeToBeDeleted(ranges, maxConsumption)
    gb = 1024.0**3
    puts "#{Time.now}: History consumes %.2fGB on disk" % [res['prevBytes'] / gb]
    if res['delete'].length > 0
      puts "#{Time.now}: History beyond max consumption of %.2fGB" % [
        maxConsumption / gb
      ]
      res['delete'].keys.each do |key|
        path = File.join(@historyPath, key)
        puts "#{Time.now}: Deleting #{path} to free up space"
        FileUtils.rm_rf(path)
        path = File.join(@historyPath, "#{key}-observer")
        puts "#{Time.now}: Deleting #{path} to free up space"
        FileUtils.rm_rf(path)
      end
      puts "#{Time.now}: History now consumes %.2fGB on disk" % [
        res['afterBytes'] / gb
      ]
    else
      puts "#{Time.now}: Max consumption %.2fGB not yet exceeded" % [
        maxConsumption / gb
      ]
    end
  end
end

require 'webrick'

class SimpleGetForm < WEBrick::HTTPServlet::AbstractServlet
  def initialize(server, tasksAnalyzer, inventoryAnalyzer,
                 erbFileContent, vcInfo, hosts_props,
                 useHttps, opts ={})
    super server
    @tasksAnalyzer = tasksAnalyzer
    @inventoryAnalyzer = inventoryAnalyzer
    @erbFileContent = erbFileContent
    @vcInfo = vcInfo
    @hosts_props = hosts_props
    @useHttps = useHttps
    @historyPath = opts[:historyPath]
    @sessionMgr = opts[:sessionMgr]
    @observerObj = VsanObserver.new(
      @tasksAnalyzer, @inventoryAnalyzer, @vcInfo, @hosts_props,
      @historyPath
    )
  end

  def do_POST(request, response)
    if request.path == "/login.html"
      return do_GET(request, response, :isLogin => true)
    else
      return do_GET(request, response)
    end
  end

  # Process the request, return response
  def do_GET(request, response, opts = {})
    staticFiles = [
      "/graphs.js", "/graphs.html",
      "/observer.css",
      "/vmw_logo_white.png",
      "/bg_pattern.png",
      "/vm-graph.svg"
    ]

    alwaysAllow = false
    if request.path == "/"
      status, content_type, body = mainpage(request)
    elsif request.path == "/logout.html"
      username = @sessionMgr.username
      error = nil
      infoMsg = nil
      successMsg = nil
      if @sessionMgr.logout(request)
        successMsg = "You are now logged out"
      else
        infoMsg = "You were not logged in"
      end
      status, content_type = [200, "text/html"]
      body = @observerObj._runERB("login.erb.html", binding)
      alwaysAllow = true
    elsif request.path == "/login.html"
      username = @sessionMgr.username
      error = nil
      infoMsg = nil
      successMsg = nil
      if opts[:isLogin]
        begin
          cookie = @sessionMgr.login(request.query['password'])
        rescue RbVmomi::VIM::InvalidLogin => ex
          error = ex.to_s
        rescue Exception => ex
          pp ex
          error = "Unexpected error"
        end
        if !error
          response.cookies.push(cookie)
          response.set_redirect(WEBrick::HTTPStatus::TemporaryRedirect, "/")
        end
      end
      status, content_type = [200, "text/html"]
      body = @observerObj._runERB("login.erb.html", binding)
      alwaysAllow = true
    elsif staticFiles.member?(request.path)
      status, content_type, body = servefile(request)
      alwaysAllow = true
    elsif request.path == "/timeranges.html"
      status, content_type, body = timerangesPage(request)
    elsif request.path == "/timeranges.json"
      status, content_type, body = timerangesPage(request, :json => true)
    # elsif request.path =~ /^\/css\//
      # status, content_type, body = servefile(request)
    elsif request.path =~ /^\/jsonstats\/(dom|pcpu|mem|lsom|vm|vit|cmmds|misc|nfs|vsansparse)\/(.*).json$/
      group = $1
      file = $2
      opts = {}
      if file =~ /^(.*)_thumb$/
        file = $1
        opts[:points] = 60
      end
      status, content_type, body = servejson(group, file, opts)
    else
      @sessionMgr.filterRequest(request)
      super(request, response)
    end

    if !alwaysAllow
      if content_type == 'text/html'
        @sessionMgr.filterRequest(request, response)
      else
        @sessionMgr.filterRequest(request)
      end
    end

    response.status = status
    response['Content-Type'] = content_type
    response.body = body
  end

  def replaceHttpWithHttps x
    if @useHttps
      x = x.gsub("http://", "https://")
    end
    x
  end

  def servefile request
    filename = "#{$analyser_lib_dirname}#{request.path}"
    content = open(filename, 'r').read
    _servefile filename, content
  end

  def _servefile filename, content
    if filename =~ /\.js$/
      return [200, "text/javascript", content]
    end
    if filename =~ /\.html$/
      return [200, "text/html", replaceHttpWithHttps(content)]
    end
    if filename =~ /\.less$/
      return [200, "text/css", content]
    end
    if filename =~ /\.css$/
      return [200, "text/css", content]
    end
    if filename =~ /\.png$/
      return [200, "image/png", content]
    end
    if filename =~ /\.svg$/
      return [200, "image/svg+xml", content]
    end
    if filename =~ /\.json$/
      return [200, "application/json", content]
    end

    [404, "text/html", "Not found"]
  end

  def json_dump out
    @inventoryAnalyzer.json_dump out
  end

  def servejson group, file, opts = {}
    points = opts[:points]
    if group == "misc"
      if file =~ /^distribution$/
        out = @inventoryAnalyzer.dumpDistribution(:points => points)
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^cbrc-(.*)$/
        hostname = $1
        out = @inventoryAnalyzer.dumpCbrc(hostname)
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^pnics-(.*)$/
        hostname = $1
        out = @inventoryAnalyzer.dumpPnics(hostname)
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^vmknic-(.*)$/
        hostname = $1
        out = @inventoryAnalyzer.dumpVmknicStats(hostname)
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^timerange$/
        out = @inventoryAnalyzer.dumpTimerange
        return [200, "text/json", json_dump(out)]
      end
    end
    if group == "vm"
      if file =~ /^list$/
        out = @inventoryAnalyzer.dumpVmList()
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^vscsi-([^-]*)-(.*)$/
        disk = $1
        vm = $2
        out = @inventoryAnalyzer.dumpVscsi(vm, disk, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
    end
    if group == "vit"
      if file =~ /^vit-list$/
        out = @inventoryAnalyzer.dumpIscsiTargetList()
        return [200, "text/json", json_dump(out)]
      end
      # per target stats
      if file =~ /^vit-vsi-target-(.*)$/
        targetAlias = $1
        out = @inventoryAnalyzer.dumpIscsiTargetTargetStats(targetAlias, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
      # per LUN stats
      if file =~ /^vit-vsi-lun-(.*)$/
        lunUuid = $1
        out = @inventoryAnalyzer.dumpIscsiTargetLunStats(lunUuid, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
      # per host stats
      if file =~ /^vit-vsi-(.*)$/
        hostname = $1
        out = @inventoryAnalyzer.dumpIscsiTargetHostStats(hostname, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
    end
    if group == "cmmds"
      if file =~ /^disks$/
        out = @inventoryAnalyzer.dumpCmmdsDisks()
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^cmmds-(.*)$/
        uuid = $1
        out = @inventoryAnalyzer.dumpCmmdsUuid(uuid)
        return [200, "text/json", json_dump(out)]
      end
    end
    if group == "dom"
      if file =~ /^domobj-(client|total|compmgr)-(.*)$/
        uuid = "#{$1}-#{$2}"
        out = @inventoryAnalyzer.dumpDom(uuid, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      elsif file =~ /^domobj-(.*)$/
        uuid = $1
        out = @inventoryAnalyzer.dumpDom(uuid, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
    end
    if group == "pcpu"
      # XXX refactory below 3 blocks in future. Without these quick fixes
      # In PCPU tab, vmnic and vmknic full graph cannot display
      if file =~ /^wdt-(.*)-(vmk.*)$/
        hostname = $1
        wdt = $2
        out = @inventoryAnalyzer.dumpWdt(hostname, wdt, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^wdt-(.*)-(vmnic.*)$/
        hostname = $1
        wdt = $2
        out = @inventoryAnalyzer.dumpWdt(hostname, wdt, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^wdt-([\d\.]*)-((tq-)?vit.*)$/
        hostname = $1
        wdt = $2
        out = @inventoryAnalyzer.dumpWdt(hostname, wdt, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^wdt-(.*)-([^-]*)$/
        hostname = $1
        wdt = $2
        out = @inventoryAnalyzer.dumpWdt(hostname, wdt, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^wdtsum-(.*)$/
        hostname = $1
        out = @inventoryAnalyzer.dumpWdtSum(hostname, :points => points)
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^pcpu-(.*)$/
        hostname = $1
        out = @inventoryAnalyzer.dumpPcpu(hostname, :points => points)
        return [200, "text/json", json_dump(out)]
      end
    end
    if group == "mem"
      if file =~ /^heaps-(.*)$/
        hostname = $1
        out = @inventoryAnalyzer.dumpHeaps(hostname, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^slabs-(.*)$/
        hostname = $1
        out = @inventoryAnalyzer.dumpSlabs(hostname, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^system-(.*)$/
        hostname = $1
        out = @inventoryAnalyzer.dumpSystemMem(hostname, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
    end
    if group == "lsom"
      if file =~ /^lsomcomp-(.*)$/
        uuid = $1
        out = @inventoryAnalyzer.dumpLsomComp(uuid, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
      # if file =~ /^lsomhost-(.*)$/
        # hostname = $1
        # out = @inventoryAnalyzer.dumpLsomHost(hostname, nil, :points => points)
        # return [200, "text/json", json_dump(out)]
      # end
      # if file =~ /^ssd-(.*)$/
        # uuid = $1
        # out = @inventoryAnalyzer.dumpSsd(uuid, nil, nil, :points => points)
        # return [200, "text/json", json_dump(out)]
      # end
      if file =~ /^plog-(.*)$/
        dev = $1
        out = @inventoryAnalyzer.dumpPlog(dev, nil, nil, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
      if file =~ /^disk-(.*)$/
        dev = $1
        out = @inventoryAnalyzer.dumpDisk(dev, nil, nil, :points => points)
        return [200, "text/json", json_dump(out)]
      end
      # if file =~ /^physdisk-(.*)-([^-]*)$/
        # hostname = $1
        # md5Dev = $2
        # out = @inventoryAnalyzer.dumpPhysDisk(hostname, nil, nil, \
                                              # md5 = md5Dev, :points => points)
        # return [200, "text/json", json_dump(out)]
      # end
    end
    if group == "vsansparse"
      out = nil
      # vsansparse uuid is in 8-8-4-4-4-12 format, which is different to normal uuid
      if file =~ /^vsansparse-(.*)-([0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/
        hostname = $1
        uuid = $2
        out = @inventoryAnalyzer.dumpVsansparse(hostname, uuid)
      elsif file =~ /^vsansparse-(.*)$/
        hostname = $1
        out = @inventoryAnalyzer.dumpVsansparse(hostname, nil)
      elsif file == "vsansparseList"
        out = @inventoryAnalyzer.dumpVsansparseList()
      elsif file == "vsansparseHosts"
        out = @inventoryAnalyzer.dumpVsansparseHosts()
      elsif file == "vsansparseMaps"
        out = @inventoryAnalyzer.vsansparsePathmap
      end
      if out
        #puts "vsansparse #{file}=[#{out}]"
        return [200, "text/json", json_dump(out)]
      end
    end
    out = @inventoryAnalyzer.dumpByFilename(group, file, :points => points)
    if out
      return [200, "text/json", json_dump(out)]
    end

    [404, "text/html", "Not found"]
  end

  def timerangesPage request, opts = {}
    if !@historyPath
      return [404, "text/html", "Not found"]
    end

    if opts[:json]
      html = JSON.dump(@observerObj._timerangeInfo())
      [200, "text/json", replaceHttpWithHttps(html)]
    else
      html = @observerObj.generate_history_html()
      [200, "text/html", replaceHttpWithHttps(html)]
    end
  end

  def mainpage request
    html = @observerObj.generate_observer_html()
    [200, "text/html", replaceHttpWithHttps(html)]
  end
end

module InventoryAnalyzerReset
  def reset
    initialize
  end
end

module TasksAnalyzerReset
  def reset
    initialize({})
  end
end

opts :observer do
  summary "Run observer"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem], :multi => :true
  opt :filename, "Output file path", :type => :string
  opt :port, "Port on which to run webserver", :type => :int, :default => 8010
  opt :run_webserver, "Run a webserver to view live stats", :type => :boolean
  opt :force, "Apply force", :type => :boolean
  opt :keep_observation_in_memory, "Keep observed stats in memory even when commands ends. Allows to resume later", :type => :boolean
  opt :generate_html_bundle, "Generates an HTML bundle after completion. Pass a location", :type => :string
  opt :interval, "Interval (in sec) in which to collect stats", :type => :int, :default => 60
  opt :max_runtime, "Maximum number of hours to collect stats. Caps memory usage.", :type => :int, :default => 2
  opt :forever, "Runs until stopped. Every --max-runtime intervals retires snapshot to disk. Pass a location", :type => :string
  opt :no_https, "Don't use HTTPS and don't require login. Warning: Insecure", :type => :boolean
  opt :ssl_protocols, "Allowed SSL protocols in comma separated list of sslv3, tlsv1, tlsv1_1, and tlsv1_2", :type => :string, :default => "tlsv1_2"
  opt :max_diskspace_gb, "Maximum disk space (in GB) to use in forever mode. Deletes old data periodically", :type => :int, :default => 5
  opt :cmmds_history, "Collect CMMDS History (Not recommended for clusters with >13K Objects)", :type => :boolean
end

def _include_observer_analyzer_files
  require 'rvc/observer/analyzer-lib'
  require 'rvc/observer/tasks-analyzer'
  require 'rvc/observer/inventory-analyzer'
  files = $".grep(/observer\/inventory-analyzer.rb/)
  files.each{|x| load(x)}
end

def observer cluster_or_host, opts
  conn = cluster_or_host.first._connection
  pc = conn.propertyCollector
  host = cluster_or_host
  entries = []
  hostUuidMap = {}

  hasClusters = cluster_or_host.any?{|x| x.is_a?(RbVmomi::VIM::ClusterComputeResource)}
  if cluster_or_host.length > 1 && hasClusters
    err "Passing in multiple clusters is not supported"
  end

  vcAbout = conn.serviceContent.about
  vcInfo = {
    'hostname' => conn.host,
    'about' => {
      'fullName' => vcAbout.fullName,
      'osType' => vcAbout.osType,
      'apiVersion' => vcAbout.apiVersion,
      'apiType' => vcAbout.apiType,
      'build' => vcAbout.build,
      'instanceUuid' => vcAbout.instanceUuid,
      'version' => vcAbout.version,
    },
  }

  if opts[:run_webserver] && !opts[:force] && opts[:no_https]
    puts "Running a webserver with unencrypted HTTP on the vCenter machine "
    puts "could pose a security risk. This tool is an experimenal debugging "
    puts "tool, which has not been audited or tested for its security."
    puts "If in doubt, you may want to create a dummy vCenter machine to run"
    puts "just this tool, instead of running the tool on your production "
    puts "vCenter machine."
    puts "In order to run the webserver, please pass --force"
    err "Force needs to be applied to run the webserver"
  end
  if opts[:run_webserver] && !opts[:force] && !opts[:no_https]
    puts "While the VSAN observer uses HTTPS and requires a login, it is an"
    puts "experimental debugging tool, which has not been audited or tested"
    puts "for its security."
    puts "If in doubt, you may want to create a dummy vCenter machine to run"
    puts "just this tool, instead of running the tool on your production "
    puts "vCenter machine."
    puts "In order to run the webserver, please pass --force"
    err "Force needs to be applied to run the webserver"
  end

  if opts[:run_webserver] && !opts[:no_https]
    supported = ["sslv3", "tlsv1", "tlsv1_1", "tlsv1_2"]

    # normalize user inputs from command line options
    protocols = opts[:ssl_protocols].split(/,/).collect(&:strip).reject(&:empty?).uniq
    if not protocols.empty?()
      invalids = protocols.reject {|x| supported.include?(x)}
      if not invalids.empty?()
        puts "Valid arguments for ssl_protocols are combination of: #{supported}"
        err "The given ssl protocol name(s) for ssl_protocols is invalid: #{invalids}"
      end
    end

    if protocols.empty?()
      protocols = ['tlsv1_2']
    end
  end

  if opts[:max_diskspace_gb] <= 0
    err "max_diskspace_gb should be an integer greater than 0"
  end

  if opts[:generate_html_bundle]
    bundle_path = opts[:generate_html_bundle]
    if Dir.exists?(bundle_path) == false
      err "Directory #{bundle_path} does not exist"
    end
    if File.directory?(bundle_path) == false
      err "#{bundle_path} is not a directory"
    end
    if File.writable?(bundle_path) == false
      err "Directory #{bundle_path} is not writable"
    end
  end

  _include_observer_analyzer_files

  inventoryAnalyzer = $inventoryAnalyzer
  tasksAnalyzer = $tasksAnalyzer

  inventoryAnalyzer ||= InventoryAnalyzer.new
  tasksAnalyzer ||= TasksAnalyzer.new({})
  inventoryAnalyzer.extend InventoryAnalyzerReset
  tasksAnalyzer.extend TasksAnalyzerReset

  file = nil
  if opts[:filename]
    file = open(opts[:filename], 'a')
  end

  foreverFile = nil
  if opts[:forever]
    foreverFilePath = opts[:forever]
    FileUtils.mkdir_p foreverFilePath
    foreverFile = open(File.join(foreverFilePath, 'observer.json'), 'a')
  end

  server = nil
  webrickThread = nil
  hosts_props = nil

  _run_with_rev(conn, "dev") do
    vsanIntSys = nil
    model = VsanModel.new(cluster_or_host,
      [
        'summary.config.product',
        'summary.hardware'
      ],
      :get_vsan_clusterdisk_info => true,
    )
    info = model.basic
    connected_hosts = info['connected_hosts']
    host = info['connected_hosts'].first
    hosts_props = info['hosts_props']
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']

    vmViews = {}
    connGroups = connected_hosts.group_by{|x| x._connection}
    connGroups.keys.each do |groupConn|
      viewMgr = groupConn.serviceContent.viewManager
      rootFolder = groupConn.serviceContent.rootFolder

      vmView = viewMgr.CreateContainerView(
        :container => rootFolder,
        :type => ['VirtualMachine'],
        :recursive => true
      )
      vmViews[groupConn] = vmView
    end

    if opts[:run_webserver]
      erbFilename = "#{$analyser_lib_dirname}/stats.erb.html"
      erbFileContent = open(erbFilename, 'r').read

      cert_name = [
       %w[CN localhost],
      ]
      opts[:use_https] = (opts[:no_https] != true)
      if opts[:use_https]
        require 'webrick/https'

        opts[:https_cert] = $rvc_https_cert
        opts[:https_pkey] = $rvc_https_pkey
        if ENV['VMWARE_CFG_DIR']
          winkey = File.join(ENV['VMWARE_CFG_DIR'], 'vmware-vpx', 'ssl', 'rui.key')
          wincert = File.join(ENV['VMWARE_CFG_DIR'], 'vmware-vpx', 'ssl', 'rui.crt')
          if File.exists?(winkey) && File.exists?(wincert)
            opts[:https_pkey] ||= winkey
            opts[:https_cert] ||= wincert
          end
        end
        puts "#{Time.now}: Spawning HTTPS server"
        certFilename = opts[:https_cert] || "/etc/vmware-vpx/ssl/rui.crt"
        pkeyFilename = opts[:https_pkey] || "/etc/vmware-vpx/ssl/rui.key"
        if opts[:https_cert] && !File.exists?(opts[:https_cert])
          err "Cert file #{opts[:https_cert]} coult not be found"
        end
        if opts[:https_pkey] && !File.exists?(opts[:https_pkey])
          err "Private key file #{opts[:https_pkey]} coult not be found"
        end
        cert = nil
        pkey = nil
        if File.exists?(certFilename) && File.exists?(pkeyFilename)
          puts "#{Time.now}: Using certificate file: #{certFilename}"
          puts "#{Time.now}: Using private key file: #{pkeyFilename}"
          cert = OpenSSL::X509::Certificate.new(File.open(certFilename).read)
          pkey = OpenSSL::PKey::RSA.new(File.open(pkeyFilename).read)
        else
          puts "#{Time.now}: No cert passed in, no VCSA cert found, generating self-signed cert"
        end

        # initially, support all op except SSLv2
        sslopts = OpenSSL::SSL::OP_ALL | OpenSSL::SSL::OP_NO_SSLv2

        # if possible, disable compression
        sslopts |= OpenSSL::SSL::OP_NO_COMPRESSION if defined?(OpenSSL::SSL::OP_NO_COMPRESSION)

        # exclude the op which does not appear in command line options
        if not protocols.include?("sslv3")
          sslopts |= OpenSSL::SSL::OP_NO_SSLv3 if defined?(OpenSSL::SSL::OP_NO_SSLv3)
        end
        if not protocols.include?("tlsv1")
          sslopts |= OpenSSL::SSL::OP_NO_TLSv1 if defined?(OpenSSL::SSL::OP_NO_TLSv1)
        end
        if not protocols.include?("tlsv1_1")
          sslopts |= OpenSSL::SSL::OP_NO_TLSv1_1 if defined?(OpenSSL::SSL::OP_NO_TLSv1_1)
        end
        if not protocols.include?("tlsv1_2")
          sslopts |= OpenSSL::SSL::OP_NO_TLSv1_2 if defined?(OpenSSL::SSL::OP_NO_TLSv1_2)
        end

        httpServerOpts = {
          :SSLEnable => true,
          :SSLCertName => cert_name,
          :SSLCertificate => cert,
          :SSLPrivateKey => pkey,
          :SSLOptions => sslopts
        }
      else
        httpServerOpts = {}
      end
      httpServerOpts[:Port] = opts[:port]

      # add .svg to default mime type
      mime_types = WEBrick::HTTPUtils::DefaultMimeTypes
      mime_types.store 'svg', 'image/svg+xml'
      httpServerOpts[:MimeTypes] = mime_types

      sessionMgr = WebrickSessionManager.new(
        conn,
        :noLogin => !opts[:use_https]
      )
      spaceManager = ObserverHistorySpaceManager.new(
        tasksAnalyzer, inventoryAnalyzer, vcInfo,
        hosts_props,
        :historyPath => opts[:forever],
      )
      server = WEBrick::HTTPServer.new(httpServerOpts)
      if opts[:use_https]
        # remove all inscure ciphers like MD5, RC4, etc.
        server.ssl_context.ciphers = "HIGH:!EDH:!aNULL:!ADH:!EXP:!MD5:!3DES:!CAMELLIA:!PSK:!SRP:@STRENGTH"
      end
      server.mount(
        "/", SimpleGetForm,
        tasksAnalyzer, inventoryAnalyzer, erbFileContent, vcInfo,
#JSON.load(JSON.dump(hosts_props))
        hosts_props, opts[:use_https],
        :historyPath => opts[:forever],
        :sessionMgr => sessionMgr,
      )
      if opts[:forever]
        server.mount(
          "/history", WEBrick::HTTPServlet::FileHandler,
          opts[:forever],
          :FancyIndexing => true,
          :DirectoryCallback => Proc.new do |req, res|
            sessionMgr.filterRequest(req, res)
          end,
          :FileCallback => Proc.new do |req, res|
            if req.path =~ /.html$/
              sessionMgr.filterRequest(req, res)
            end
            sessionMgr.filterRequest(req)
          end
        )
      end
      if Dir.exists?(File.join($analyser_lib_dirname, "externallibs"))
        server.mount(
          "/externallibs", WEBrick::HTTPServlet::FileHandler,
          File.join($analyser_lib_dirname, "externallibs"),
          :FancyIndexing => true
        )
      end

      webrickThread = Thread.new do
        server.start
      end
    end

    puts "Press <Ctrl>+<C> to stop observing at any point ..."
    puts

    startTime = Time.now
    lastResetTime = startTime
    begin
      while true
        if !opts[:forever] && (Time.now - startTime) >= opts[:max_runtime] * 3600
          break
        end
        puts "#{Time.now}: Collect one inventory snapshot"
        t1 = Time.now
        begin
          observation = _observe_snapshot(
            host, connected_hosts, vmViews, hosts_props, opts[:cmmds_history]
          )
          observation['snapshot']['vcinfo'] = vcInfo
          observation['timestamp'] = Time.now.to_f
          if opts[:forever]
            foreverFile.write(JSON.dump(observation) + "\n")
            #foreverFile.flush()
          end
          if file
            # JSON.dump() can serialize Rbvmomi data object to json string
            # after rbvmomi change 9087167afefdfb710cf61c32ee4ea5c5a550b99f
            file.write(JSON.dump(observation) + "\n")
            file.flush()
          end
          # write to file and also update live stats page
          puts "#{Time.now}: Live-Processing inventory snapshot"
          tasksAnalyzer.processTrace(observation)
          inventoryAnalyzer.processInventorySnapshot(observation)
        rescue Interrupt
          raise
        rescue Exception => ex
          puts "#{Time.now}: Got exception: #{ex.class}: #{ex.message}"
          ex.backtrace.each{|x| puts "  #{x}"}
        end

        if opts[:forever]# and opts[:single_json] #new single_json
          if (t1 - lastResetTime) >= opts[:max_runtime] * 60 * 60 #every max_runtime hour
            begin
              VsanObserver.new(
                tasksAnalyzer, inventoryAnalyzer,
                vcInfo, hosts_props,
                opts[:forever]
              )#.generate_observer_files(foreverFilePath)
              tasksAnalyzer.reset
              inventoryAnalyzer.reset
              foreverFile.close()
              
              foreverFile = open(File.join(foreverFilePath, 'observer.json'), 'a')

              #spaceManager.deleteOldTimeranges(opts[:max_diskspace_gb] * 1024**3) # 500GB

              lastResetTime = t1
            rescue Exception => ex
              puts "#{Time.now}: Failed to generate HTML bundle: #{ex.class}: #{ex.message}"
            end
          end
        end

        t2 = Time.now

        intervalTime = opts[:interval]
        time = t2 - t1
        sleepTime = intervalTime - time
        if sleepTime <= 0.0
          puts "#{Time.now}: Collection took %.2fs (> %.2fs), no sleep ..." % [
            time, intervalTime
          ]
        else
          puts "#{Time.now}: Collection took %.2fs, sleeping for %.2fs" % [
            time, sleepTime
          ]
          puts "#{Time.now}: Press <Ctrl>+<C> to stop observing"
          sleep(sleepTime)
        end
      end
    rescue Interrupt
      puts "#{Time.now}: Execution interrupted, wrapping up ..."
    ensure
      if foreverFile
        foreverFile.close()
      end
    end
    #pp res
    vmViews.values.each{|x| x.DestroyView()}

  end

  if file
    file.close()
  end
  if server
    server.shutdown
    webrickThread.join
  end
  if opts[:generate_html_bundle]
    begin
      VsanObserver.new(
        tasksAnalyzer, inventoryAnalyzer,
        vcInfo, hosts_props,
        nil
      ).generate_observer_bundle(opts[:generate_html_bundle])
    rescue Exception => ex
      puts "#{Time.now}: Failed to generate HTML bundle: #{ex.class}: #{ex.message}"
    end
  end

  if opts[:keep_observation_in_memory]
    $inventoryAnalyzer = inventoryAnalyzer
    $tasksAnalyzer = tasksAnalyzer
  else
    $inventoryAnalyzer = nil
    $tasksAnalyzer = nil
  end
end

opts :observer_process_statsfile do
  summary "Analyze an offline observer stats file and produce static HTML"
  arg :statsfile, nil, :type => :string
  arg :outputpath, nil, :type => :string
  opt :max_traces, "Only process this many traces", :type => :int
end

def observer_process_statsfile statsfile, outputpath, opts = {}
  _include_observer_analyzer_files

  FileUtils.mkdir_p(outputpath)

  inventoryAnalyzer = InventoryAnalyzer.new
  tasksAnalyzer = TasksAnalyzer.new({})

  if statsfile =~ /\.gz$/
    fp = Zlib::GzipReader.open(statsfile)
  else
    fp = open(statsfile)
  end

  puts "#{Time.now}: Processing stats line-by-line"
  vcInfo = nil
  hosts_props = nil
  i = 0
  fp.each_line do |line|
    begin
      observation = rvc_load_json(line)
    rescue
      puts "#{Time.now}: Skipping bad JSON line"
      next
    end
    snap = observation['snapshot']
    if !vcInfo && snap
      vcInfo = snap['vcinfo']
    end
    if !hosts_props && snap && snap['inventory']
      hosts_props = snap['inventory']['hosts']
    end
    tasksAnalyzer.processTrace(observation)
    inventoryAnalyzer.processInventorySnapshot(observation)
    i += 1
    if i % 10 == 0
      puts "#{Time.now}: Processed #{i} traces so far"
    end

    if opts[:max_traces] && i >= opts[:max_traces]
      puts "#{Time.now}: Got as many traces as desired, skipping rest"
      break
    end
  end
  fp.close

  puts "#{Time.now}: Spitting out result ..."
  forever = nil
  VsanObserver.new(
    tasksAnalyzer, inventoryAnalyzer,
    vcInfo, hosts_props,
    forever
  ).generate_observer_files(outputpath)
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
    vsan_enabled_hosts = model.basic['vsan_enabled_hosts']
    hosts_props = model.basic['hosts_props']
    if vsan_enabled_hosts.length == 0
      err "Couldn't find any vsan enabled hosts"
    end
    host = vsan_enabled_hosts.first
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

    puts "#{Time.now}: Querying all VMs on VSAN ..."
    ds_list = host.datastore
    ds_props = pc.collectMultiple(ds_list, 'name', 'summary.type')
    ds = ds_props.select{|k, x| x['summary.type'] == "vsan"}.keys.first

    vms = ds.vm
    vmsProps = pc.collectMultiple(vms,
      'name', 'runtime.connectionState',
      'config.hardware.device', 'summary.config', 'layoutEx.file',
    )

    iter = 0
    while (iter == 0) || opts[:refresh_rate]
      puts "#{Time.now}: Querying all objects in the system from #{hostname} ..."

      result = vsanIntSys.query_syncing_vsan_objects({})
      if !result
        err "Server failed to gather syncing objects"
      end
      objects = result['dom_objects']

      puts "#{Time.now}: Got all the info, computing table ..."
      objects = objects.map do |uuid, objInfo|
        obj = objInfo['config']
        comps = _components_in_dom_config(obj['content'])
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

      vmToObjMap = _compute_vm_to_obj_map(vms, vmsProps, obj_uuids)
      vm_obj_uuids = vmToObjMap.values.map{|x| x.keys}.flatten.uniq
      non_vm_obj_uuids = obj_uuids - vm_obj_uuids
      if non_vm_obj_uuids.length > 0
        vmToObjMap['Unassociated'] = Hash[non_vm_obj_uuids.map{|x| [x,x]}]
      end

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



opts :vm_perf_stats do
  summary "VM perf stats"
  arg :vms, nil, :lookup => [VIM::VirtualMachine], :multi => true
  opt :interval, "Time interval to compute average over", :type => :int, :default => 20
  opt :show_objects, "Show objects that are part of VM", :type => :boolean
end

def vm_perf_stats vms, opts
  conn = vms.first._connection
  pc = conn.propertyCollector
  cluster = vms.first.runtime.host.parent
  hosts = cluster.host

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
      [props['name'], props['configManager.vsanSystem']]
    end]
    clusterInfos = pc.collectMultiple(vsanSysList.values,
                                      'config.clusterInfo')
    hostUuidMap = Hash[vsanSysList.map do |hostname, sys|
      [clusterInfos[sys]['config.clusterInfo'].nodeUuid, hostname]
    end]
    hostNameToMoMap = Hash[hosts_props.map do |host, props|
      [props['name'], host]
    end]

    entries = nil

    puts "#{Time.now}: Querying info about VMs ..."
    vmsProps = pc.collectMultiple(vms,
      'name', 'runtime.connectionState',
      'config.hardware.device', 'summary.config', 'layoutEx.file'
    )

    obj_uuids = []
    vms.each do |vm|
      obj_uuids += _get_vm_obj_uuids(vm, vmsProps).keys
    end

    puts "#{Time.now}: Querying VSAN objects used by the VMs ..."

    objects = vsanIntSys.query_cmmds(obj_uuids.map do |uuid|
      {:type => 'CONFIG_STATUS', :uuid => uuid}
    end)
    if !objects
      err "Server failed to gather CONFIG_STATUS entries"
    end

    objByHost = {}
    objects.each do |entry|
      host = hostUuidMap[entry['owner']]
      if !host
        next
      end
      host = hostNameToMoMap[host]
      if !host
        next
      end
      objByHost[host] ||= []
      objByHost[host] << entry['uuid']
    end

    def fetchStats(objByHost, hosts_props)
      stats = {}
      objByHost.each do |host, obj_uuids|
        vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']

        res = vsanIntSys.QueryVsanStatistics(:labels => obj_uuids.map do |uuid|
          "dom-object:#{uuid}"
        end)
        res = rvc_load_json(res)

        obj_uuids.each do |uuid|
          stats[uuid] = res['dom.owners.selected.stats'][uuid]
          if stats[uuid]
            stats[uuid]['ts'] = res['dom.owners.selected.stats-taken']
          end
        end
      end
      stats
    end

    puts "#{Time.now}: Fetching stats counters once ..."
    stats1 = fetchStats(objByHost, hosts_props)
    sleepTime = opts[:interval]
    puts "#{Time.now}: Sleeping for #{sleepTime} seconds ..."
    sleep(sleepTime)
    puts "#{Time.now}: Fetching stats counters again to compute averages ..."
    stats2 = fetchStats(objByHost, hosts_props)

    puts "#{Time.now}: Got all data, computing table"
    stats = {}
    objects.each do |entry|
      uuid = entry['uuid']
      deltas = Hash[stats2[uuid].keys.map do |key|
        [key, stats2[uuid][key] - stats1[uuid][key]]
      end]
      deltaT = deltas['ts']
      stats[uuid] = deltas.merge({
        :readIops => deltas['readCount'] / deltaT,
        :writeIops => deltas['writeCount'] / deltaT,
        :readTput => deltas['readBytes'] / deltaT,
        :writeTput => deltas['writeBytes'] / deltaT,
        :readLatency => 0,
        :writeLatency => 0,
      })
      if deltas['readCount'] > 0
        stats[uuid][:readLatency] = deltas['readLatencySumUs'] / deltas['readCount']
      end
      if deltas['writeCount'] > 0
        stats[uuid][:writeLatency] = deltas['writeLatencySumUs'] / deltas['writeCount']
      end
    end

    t = Terminal::Table.new()
    t << [
      'VM/Object',
      'IOPS',
      'Tput (KB/s)',
      'Latency (ms)'
    ]
    t.add_separator
    vms.each do |vm|
      vmProps = vmsProps[vm]
      vm_obj_uuids = _get_vm_obj_uuids(vm, vmsProps)

      if !opts[:show_objects]
        vmStats = {}
        vmStats[:readLatency] ||= []
        vmStats[:writeLatency] ||= []
        [:readIops, :writeIops, :readTput, :writeTput].each do |key|
          vmStats[key] ||= 0.0
        end

        vm_obj_uuids.each do |uuid, path|
          path = path.gsub(/^\[([^\]]*)\] /, "")
          objStats = stats[uuid]
          if !objStats
            next
          end
          [:readIops, :writeIops, :readTput, :writeTput].each do |key|
            vmStats[key] += (objStats[key] || 0.0)
          end
          vmStats[:readLatency] << (objStats[:readLatency] * objStats[:readIops])
          vmStats[:writeLatency] << (objStats[:writeLatency] * objStats[:writeIops])
        end
        if vmStats[:readLatency].length > 0 && vmStats[:readIops] > 0.0
          vmStats[:readLatency] = vmStats[:readLatency].sum / vmStats[:readIops]
        else
          vmStats[:readLatency] = 0.0
        end
        if vmStats[:writeLatency].length > 0 && vmStats[:writeIops] > 0.0
          vmStats[:writeLatency] = vmStats[:writeLatency].sum / vmStats[:writeIops]
        else
          vmStats[:writeLatency] = 0.0
        end

        t << [
          vmProps['name'],
          [
            "%.1fr" % [vmStats[:readIops]],
            "%.1fw" % [vmStats[:writeIops]],
          ].join("/"),
          [
            "%.1fr" % [vmStats[:readTput] / 1024.0],
            "%.1fw" % [vmStats[:writeTput] / 1024.0],
          ].join("/"),
          [
            "%.1fr" % [vmStats[:readLatency] / 1000.0],
            "%.1fw" % [vmStats[:writeLatency] / 1000.0],
          ].join("/"),
        ]
      else
        t << [
          vmProps['name'],
          "",
          "",
          "",
        ]
        vm_obj_uuids.each do |uuid, path|
          path = path.gsub(/^\[([^\]]*)\] /, "")
          objStats = stats[uuid]
          if !objStats
            t << [
              "   %s" % (path || uuid),
              "N/A","N/A","N/A",
            ]
            next
          end
          t << [
            "   %s" % (path || uuid),
            [
              "%.1fr" % [objStats[:readIops]],
              "%.1fw" % [objStats[:writeIops]],
            ].join("/"),
            [
              "%.1fr" % [objStats[:readTput] / 1024.0],
              "%.1fw" % [objStats[:writeTput] / 1024.0],
            ].join("/"),
            [
              "%.1fr" % [objStats[:readLatency] / 1000.0],
              "%.1fw" % [objStats[:writeLatency] / 1000.0],
            ].join("/"),
          ]
        end
      end
    end
    # t.add_separator
    # t << [
      # 'Total',
      # objGrandTotal,
      # "%.2f GB" % (bytesToSyncGrandTotal.to_f / 1024**3),
      # #"%.2f min" % (recoveryETATotal.to_f / 60),
    # ]
    puts t
  end
end


opts :enter_maintenance_mode do
  summary "Put hosts into maintenance mode\n" +
          "Choices for vsan-mode: ensureObjectAccessibility, evacuateAllData, noAction"
  arg :host, nil, :lookup => VIM::HostSystem, :multi => true
  opt :timeout, "Timeout (in seconds)", :default => 0
  opt :evacuate_powered_off_vms, "Evacuate powered off vms", :type => :boolean
  opt :no_wait, "Don't wait for Task to complete", :type => :boolean
  opt :vsan_mode, "Actions to take for VSAN backed storage", :type => :string, :default => "ensureObjectAccessibility"
end

def enter_maintenance_mode hosts, opts
  vsanChoices = ['ensureObjectAccessibility', 'evacuateAllData', 'noAction']
  if !vsanChoices.member?(opts[:vsan_mode])
    err "VSAN mode can only be one of these: #{vsanChoices}"
  end
  tasks = []
  conn = hosts[0]._connection
  _run_with_rev(conn, "dev") do
    tasks = hosts.map do |host|
      host.EnterMaintenanceMode_Task(
        :timeout => opts[:timeout],
        :evacuatePoweredOffVms => opts[:evacuate_powered_off_vms],
        :maintenanceSpec => {
          :vsanMode => {
            :objectAction => opts[:vsan_mode],
          }
        }
      )
    end
  end

  if opts[:no_wait]
    # Do nothing
  else
    results = progress(tasks)

    results.each do |task, error|
      if error.is_a?(VIM::LocalizedMethodFault)
        state, entityName, name = task.collect('info.state',
                                               'info.entityName',
                                               'info.name')
        puts "#{name} #{entityName}: #{error.fault.class.wsdl_name}: #{error.localizedMessage}"
        error.fault.faultMessage.each do |msg|
          puts "  #{msg.key}: #{msg.message}"
        end

      end
    end
  end
end

def _parseJson json
  if json == "BAD"
    return nil
  end
  begin
    json = rvc_load_json(json)
  rescue
    nil
  end
end

def _assessAvailabilityByStatus state
  mask = {
    'DATA_AVAILABLE' => (1 << 0),
    'QUORUM' => (1 << 1),
    'PERF_COMPLIANT' => (1 << 2),
    'INCOMPLETE' => (1 << 3),
  }
  Hash[mask.map{|k,v| [k, (state & v) != 0]}]
end

class RVC::VsanModel
  attr_reader :basic

  def initialize cluster_or_hosts, hosts_props_names = [], opts = {}
    @conn = cluster_or_hosts.first._connection
    @pc = @conn.propertyCollector

    if !opts[:allow_multiple_clusters]
      hasClusters = cluster_or_hosts.any?{|x| x.is_a?(RbVmomi::VIM::ClusterComputeResource)}
      if cluster_or_hosts.length > 1 && hasClusters
        raise "Passing in multiple clusters is not supported"
      end
    end

    @basic = gather_vsan_hosts_info(cluster_or_hosts, hosts_props_names, opts)
  end

  def log x
    puts "#{Time.now}: #{x}"
  end

  def gather_vsan_hosts_info(cluster_or_host, hosts_props_names, opts = {})
    conn = cluster_or_host.first._connection
    pc = conn.propertyCollector

    if cluster_or_host[0].is_a?(VIM::ComputeResource)
      clusters_props = pc.collectMultiple(cluster_or_host, 'host')
      hosts = clusters_props.map{|c,p| p['host']}.flatten
    else
      hosts = cluster_or_host
    end
    witness_info = nil
    if $VSAN_STRETCHEDCLUSTER_SUPPORTED
      if cluster_or_host[0].is_a?(VIM::ClusterComputeResource)
        witness_info = get_witness_host(cluster_or_host[0])
        if !witness_info.nil?
          hosts << witness_info[:host]
        end
      end
    end

    hosts = hosts.uniq
    if hosts.empty?
      RVC::Util::err "No host specified to query, stop current operation."
    end

    groups = cluster_or_host.group_by{|x| x._connection}
    if groups.length > 1
      out = {}
      groups.each do |conn, objects|
        res = gather_vsan_hosts_info(objects, hosts_props_names, opts)
        res.each do |k,v|
          if v.is_a?(Hash)
            out[k] ||= {}
            out[k].merge!(v)
          elsif v.is_a?(Array)
            out[k] ||= []
            out[k] += v
          else
            RVC::Util::err "Unexpected type #{v.class} for key #{k}"
          end
        end
      end
      return out
    end


    hosts_props_names = (hosts_props_names + [
      'name',
      'runtime.connectionState',
      'configManager.vsanSystem',
      'configManager.vsanInternalSystem',
      'config.product'
    ]).uniq
    hosts_props = pc.collectMultiple(hosts, *hosts_props_names)
    connected_hosts = hosts_props.select do |k,v|
      v['runtime.connectionState'] == 'connected'
    end.keys
    host = connected_hosts.first
    if !host
      RVC::Util::err "Couldn't find any connected hosts"
    end
    vsan_enabled_hosts = hosts_props.select do |k,v|
      v['runtime.connectionState'] == 'connected' && \
      !v['configManager.vsanSystem'].nil? && \
      !v['configManager.vsanSystem'].config.nil? && \
      v['configManager.vsanSystem'].config.enabled && \
      (witness_info.nil? || v['configManager.vsanSystem']['config.clusterInfo'].nodeUuid != witness_info[:nodeUuid])
    end.keys
    #if !vsan_enabled_hosts.first
    #  RVC::Util::err "Couldn't find any enabled hosts"
    #end
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
    vsanSysList = Hash[hosts_props.map do |host, props|
      [props['name'], props['configManager.vsanSystem']]
    end]
    if opts[:get_vsan_clusterdisk_info]
      clusterInfos = pc.collectMultiple(vsanSysList.values,
        'config.clusterInfo',
        'config.storageInfo.diskMapping'
      )
      hostUuidMap = Hash[vsanSysList.map do |hostname, sys|
        [clusterInfos[sys]['config.clusterInfo'].nodeUuid, hostname]
      end]

      vsanSysList.map do |hostname, sys|
        diskMappings = clusterInfos[sys]['config.storageInfo.diskMapping']
        host = hosts_props.find{|k,v| v['name'] == hostname}[0]
        disks = []
        diskMappings.each do |diskMapping|
          diskMapping.nonSsd.each{|hdd| disks << hdd.to_dict}
          disks << diskMapping.ssd.to_dict
        end
        disks.each do |disk|
          cap = disk['capacity']
          disk['size'] = cap['blockSize'] * cap['block']
        end
        hosts_props[host]['disks'] = disks
      end
    end

    {
      'hosts' => hosts,
      'connected_hosts' => connected_hosts,
      'vsan_enabled_hosts' => vsan_enabled_hosts,
      'hosts_props' => hosts_props,
      'clusterInfos' => clusterInfos,
      'hostUuidMap' => hostUuidMap,
      'witness_info' => witness_info
    }
  end


  # Detect partitions:
  # We need to ask every host which other hosts it believes to share a
  # VSAN cluster (partition) with. This is a call down to ESX, so we spawn
  # one connection and one thread per host to parallelize. We detect
  # partitions by grouping VMs based on quoting the same cluster members.
  def get_partitions(ignoreError = false)
    hosts_props = @basic['hosts_props']
    connected_hosts = @basic['connected_hosts']
    hosts_props.map do |host, props|
      if !connected_hosts.member?(host)
        next
      end
      Thread.new do
        begin
          props.delete('exception')
          vsanSys = props['configManager.vsanSystem']
          c1 = @conn.spawn_additional_connection
          vsanSys = vsanSys.dup_on_conn(c1)
          res = vsanSys.QueryHostStatus()
          props['vsanCluster'] = res
        rescue Exception => ex
          error = "Failed to gather host status from #{props['name']}: #{ex.class}: #{ex.message}."
          if !ignoreError
            hosts_props[host]['exception'] = "Error detecting network partitions for the cluster. #{error}"
          else
            puts "#{error}. Skipping the host."
          end
        end
      end
    end.compact.each{|t| t.join}
    if !ignoreError
      first_exception = nil
      err_hosts_props = hosts_props.each do |h, p|
        if connected_hosts.member?(h) && p['exception']
          first_exception ||= p['exception']
          # clean up the exception
          p.delete('exception')
        end
      end
      if first_exception
        raise first_exception
      end
    end
    partitions = hosts_props.select do |h, p|
      connected_hosts.member?(h) && p['vsanCluster']
    end.group_by{|h, p| p['vsanCluster'].memberUuid}
    partitions
  end

  def _perform_object_analysis obj, liveDisks, liveComps, opts = {}
    comps = VsanHelperMethods._components_in_dom_config(obj['content'])
    obj['comps'] = comps
    obj['rvc_num_healthy'] = 0
    obj['rvc_num_active'] = 0
    obj['rvc_num_valid_votes'] = 0
    obj['rvc_total_votes'] = 0
    obj['rvc_num_deleted'] = 0

    comps.each do |comp|
      state = comp['attributes']['componentState']
      bytesToSync = comp['attributes']['bytesToSync'] || 0
      resync = [10, 6].member?(state) && bytesToSync != 0

      ignore = (opts[:ignore_node_uuid] &&
                comp['attributes']['ownerId'] == opts[:ignore_node_uuid])
      comp['rvc_is_resync'] = resync
      # RECONFIGURING(10) also counts towards quorum, so consider it
      # "active".
      comp['rvc_is_active'] = ignore || (state == 5)
      # Should we count resyncing as healthy?  For now, lets do that.
      comp['rvc_is_healthy'] = comp['rvc_is_active'] ||
                               comp['rvc_is_resync']
      comp['rvc_is_deleted'] = false

      if comp['rvc_is_healthy']
        obj['rvc_num_healthy'] += 1
      end
      comp['rvc_votes'] = comp['attributes']['nVotes'] || 1
      if comp['rvc_votes'] == 0
        comp['rvc_votes'] = 1
      end
      obj['rvc_total_votes'] += comp['rvc_votes']
      if comp['rvc_is_active']
        obj['rvc_num_active'] += 1
      end
      # Votes are counted only when the comp is healthy
      if comp['rvc_is_healthy']
        obj['rvc_num_valid_votes'] += comp['rvc_votes']
      end
      if !comp['rvc_is_healthy'] &&
         liveDisks.member?(comp['diskUuid']) &&
         !liveComps.member?(comp['componentUuid'])
        # A component is considered deleted if it's disk is present
        # and the component is not present in CMMDS.
        comp['rvc_is_deleted'] = true
        obj['rvc_num_deleted'] += 1
      end
    end

    # An object can be orphaned if it is deleted while a minority of
    # components are absent.  To consider this an orphan, the total
    # number of provably deleted components must be a quorum.
    # If we have some deleted comps, but not a quorum, then mark it
    # as an orphanCandidate instead of a full orphan.  Orphan candidates
    # still go into the normal results table.
    # XXX: Do we need to consider votes?
    numDeleted = obj['rvc_num_deleted']
    isOrphan = numDeleted > 0 && numDeleted > comps.length / 2
    if isOrphan
      obj['isOrphan'] = true
    elsif numDeleted > 0
      obj['isOrphanCandidate'] = true
    end

    validVotes = obj['rvc_num_valid_votes']
    totalVotes = obj['rvc_total_votes']
    obj['hasQuorum'] = validVotes > (totalVotes / 2)
    if obj['rvc_num_active'] == comps.length
      obj['raidAvailable'] = true
    else
      obj['raidAvailable'] = _is_dom_subtree_available(obj['content'])
    end
    obj['hasLiveness'] = obj['hasQuorum'] && obj['raidAvailable']
  end

  def _is_dom_subtree_available domConfig
    type = domConfig['type']
    keys = domConfig.keys.select{|x| x =~ /^child-\d+$/}
    if type == 'Configuration'
      keys = keys.select{|k| domConfig[k]['type'] != 'Witness'}
      return keys.all?{|k| _is_dom_subtree_available(domConfig[k])}
    end

    childs = keys.map{|k| _is_dom_subtree_available(domConfig[k])}
    if type == 'RAID_1'
      return childs.member?(true)
    elsif type == 'RAID_0'
      return !childs.member?(false)
    elsif type == 'RAID_5'
      # RAID5 can tolerate 1 failure
      return childs.count(false) <= 1
    elsif type == 'RAID_6'
      # RAID6 can tolerate 2 failures
      return childs.count(false) <= 2
    elsif type == 'Concatenation'
      return !childs.member?(false)
    elsif type == 'Component' || type == 'Witness'
      return [5].member?(domConfig['attributes']['componentState'])
    else
      raise "Unexpected DOM tree node #{type}"
    end
  end

  def get_first_enabled_host
    host = @basic['vsan_enabled_hosts'].first
    if !host
      RVC::Util::err "Couldn't find any vsan enabled hosts"
    end
    host
  end

  def _get_vsan_ds
    # XXX: In theory we could have multiple VSAN datastores, and we
    # should find all. And not all hosts have access to VSAN ...
    # But for now this simple logic will do
    host = get_first_enabled_host
    ds_list = host.datastore
    @ds_props = @pc.collectMultiple(ds_list, 'name', 'summary.type')
    ds = @ds_props.select{|k, x| x['summary.type'] == "vsan"}.keys.first
    [ds]
  end

  def get_vsan_ds
    @vsan_ds ||= _get_vsan_ds
  end

  def _get_vsan_vms props
    log "Querying all VMs on VSAN ..."
    ds_props = @pc.collectMultiple(get_vsan_ds, 'vm')
    @vsan_vms = ds_props.map{|ds, p| p['vm']}.flatten
    props = (props + ['name', 'runtime.connectionState',
      'config.hardware.device', 'summary.config', 'layoutEx.file'
    ]).uniq
    @vms_props = @pc.collectMultiple(@vsan_vms, *props)
  end

  def get_vsan_vms props = []
    if @vms_props_props && @vms_props_props != props
      @vms_props = nil
    end
    @vms_props_props = props
    @vms_props ||= _get_vsan_vms(props)
  end

  def _get_cmmds_dom_objects
    # XXX: Deal with multiple VSANs or partitions
    host = get_first_enabled_host
    host_props = @basic['hosts_props'][host]
    hostname = host_props['name']
    vsanIntSys = host_props['configManager.vsanInternalSystem']
    log "Querying all objects in the system from #{hostname} ..."

    objects = vsanIntSys.query_cmmds([
      {:type => 'DOM_OBJECT'}
    ])
    if !objects
      raise "Server failed to gather DOM_OBJECT entries"
    end
    objects
  end

  def get_cmmds_dom_objects opts = {}
    @dom_objects ||= _get_cmmds_dom_objects
    if opts[:perform_analysis]
      liveDisks = self.get_cmmds_disk.select do |disk|
        disk['health'] == "Healthy"
      end.map do |disk|
        disk['uuid']
      end

      liveComps = self.get_cmmds_components.select do |comp|
        comp['health'] == "Healthy"
      end.map do |comp|
        comp['uuid']
      end

      @dom_objects.each do |obj|
        _perform_object_analysis(
          obj, liveDisks, liveComps,
          :ignore_node_uuid => opts[:ignore_node_uuid]
        )
      end
    end
    @dom_objects
  end

  def _get_cmmds_disks
    # XXX: Deal with multiple VSANs or partitions
    host = get_first_enabled_host
    host_props = @basic['hosts_props'][host]
    hostname = host_props['name']
    vsanIntSys = host_props['configManager.vsanInternalSystem']
    log "Querying all disks in the system from #{hostname} ..."

    objects = vsanIntSys.query_cmmds([
      {:type => 'DISK'}
    ])
    if !objects
      raise "Server failed to gather DISK entries"
    end
    objects
  end

  def get_cmmds_disk
    @cmmds_disks ||= _get_cmmds_disks
  end

  def _get_cmmds_components
    # XXX: Deal with multiple VSANs or partitions
    host = get_first_enabled_host
    host_props = @basic['hosts_props'][host]
    hostname = host_props['name']
    vsanIntSys = host_props['configManager.vsanInternalSystem']
    log "Querying all components in the system from #{hostname} ..."

    objects = vsanIntSys.query_cmmds([
      {:type => 'LSOM_OBJECT'}
    ])
    if !objects
      raise "Server failed to gather LSOM_OBJECT entries"
    end
    objects
  end

  def get_cmmds_components
    @cmmds_components ||= _get_cmmds_components
  end

  def _get_physical_vsan_disks
    host = get_first_enabled_host
    host_props = @basic['hosts_props'][host]
    hostname = host_props['name']
    vsanSys = host_props['configManager.vsanSystem']

    disks = {}
    @basic['connected_hosts'].map do |host|
      Thread.new do
        vsanIntSys = @basic['hosts_props'][host]['configManager.vsanInternalSystem']

        hostDisks = vsanIntSys.QueryPhysicalVsanDisks(:props => [
          'lsom_objects_count',
          'uuid',
          'isSsd',
          'capacity',
          'capacityUsed',
          'capacityReserved',
          'iops',
          'iopsReserved',
          'disk_health',
          'formatVersion',
          'publicFormatVersion',
          'ssdCapacity',
          'self_only',
        ])
        if hostDisks == "BAD"
          raise "Server failed to gather VSAN disk info"
        end
        begin
          hostDisks = JSON.load(hostDisks)
        rescue
          err "Server didn't provide VSAN disk info: #{disks}"
        end
        disks.merge!(hostDisks)
      end
    end.each{|t| t.join}

    disks.each do |uuid, x|
      health = "N/A"
      if x['disk_health'] && x['disk_health']['healthFlags']
        flags = x['disk_health']['healthFlags']
        health = []
        {
          4 => "FAILED",
          5 => "OFFLINE",
          6 => "DECOMMISSIONED",
        }.each do |k, v|
          if flags & (1 << k) != 0
            health << v
          end
        end
        if health.length == 0
          health = "OK"
        else
          health = health.join(", ")
        end
      end
      x['rvc_health_str'] = health

      x['fullness'] = (x['capacityUsed'].to_f / x['capacity']).round(2)
    end

    disks
  end

  def get_physical_vsan_disks
    @physical_vsan_disks ||= _get_physical_vsan_disks
  end

  def _query_limits
    hosts_props = @basic['hosts_props']
    lock = Mutex.new
    all_disks = {}
    puts "#{Time.now}: Querying limit stats from all hosts ..."
    hosts_props.map do |host, props|
      if props['runtime.connectionState'] != 'connected' || !props['configManager.vsanSystem'].config.enabled
        next
      end
      hosts_props[host]['profiling'] = {}
      Thread.new do
        vsanIntSys = props['configManager.vsanInternalSystem']
        conn = vsanIntSys._connection
        c1 = conn.spawn_additional_connection
        vsanIntSys2 = vsanIntSys.dup_on_conn(c1)
        begin
          Timeout.timeout(60) do
            t1 = Time.now
            res = vsanIntSys2.query_vsan_statistics(
              :labels => ['rdtglobal', 'lsom-node', 'lsom']
            )
            t2 = Time.now
            hosts_props[host]['profiling']['rdtglobal'] = t2 - t1
            hosts_props[host]['rdtglobal'] = res['rdt.globalinfo']
            hosts_props[host]['lsom.node'] = res['lsom.node']
            hosts_props[host]['lsom.disks'] = res['lsom.disks']
          end
        rescue Exception => ex
          puts "Failed to gather RDT info from #{props['name']}: #{ex.class}: #{ex.message}"
        end

        begin
          Timeout.timeout(60) do
            t1 = Time.now
            res = vsanIntSys2.query_vsan_statistics(
              :labels => ['dom', 'dom-objects-counts']
            )
            numOwners = res['dom.owners.count'].keys.length
            t2 = Time.now
            hosts_props[host]['profiling']['domstats'] = t2 - t1
            hosts_props[host]['dom'] = {
              'numClients'=> res['dom.clients'].keys.length,
              'numOwners'=> numOwners,
            }
          end
        rescue Exception => ex
          puts "Failed to gather DOM info from #{props['name']}: #{ex.class}: #{ex.message}"
        end

        begin
          Timeout.timeout(90) do
            t1 = Time.now
            disks = vsanIntSys2.QueryPhysicalVsanDisks(:props => [
              'lsom_objects_count',
              'uuid',
              'isSsd',
              'capacity',
              'capacityUsed',
            ])
            t2 = Time.now
            hosts_props[host]['profiling']['physdisk'] = t2 - t1
            disks = JSON.load(disks)

            # Getting the data from all hosts is kind of overkill, but
            # this way we deal with partitions and get info on all disks
            # everywhere. But we have duplicates, so need to merge.
            lock.synchronize do
              all_disks.merge!(disks)
            end
          end
        rescue Exception => ex
          puts "Failed to gather disks info from #{props['name']}: #{ex.class}: #{ex.message}"
        end
      end
    end.compact.each{|t| t.join}

    hosts = @basic['connected_hosts']
    @basic['hosts'].each do |host|
      hosts_props[host]['components'] ||= 0
    end
    disks = all_disks
    vsan_disks_info = {}
    vsan_disks_info.merge!(
      VsanHelperMethods._vsan_host_disks_info(
        Hash[hosts.map{|h| [h, hosts_props[h]['name']]}]
      )
    )
    disks.each do |k, v|
      v['esxcli'] = vsan_disks_info[v['uuid']]
      if v['esxcli']
        v['host'] = v['esxcli']._get_property :host

        hosts_props[v['host']]['components'] ||= 0
        hosts_props[v['host']]['components'] += v['lsom_objects_count']
        hosts_props[v['host']]['disks'] ||= []
        hosts_props[v['host']]['disks'] << v
      end
    end

    all_disks
  end

  def query_limits
    @all_vsan_disks ||= _query_limits
  end

  def _vsan_ssd_device_mapping vsanSys, vsanIntSys, nodeUuid
    disks = vsanIntSys.query_physical_vsan_disks(:props => [
      'uuid',
      'isSsd',
      'owner',
      'formatVersion',
    ])
    disks = Hash[disks.values.group_by{|x| x['owner']}.map do |owner, hostDisks|
      ssds = hostDisks.select{|disk| disk['isSsd'] == 1}
      [owner, ssds]
    end]
    disks = disks[nodeUuid] || []
    physicalDisks = vsanSys.QueryDisksForVsan()
    physicalDisks = physicalDisks.select{|x| x.state =~ /^inUse$/ && x.disk.ssd}
    physicalDisks = Hash[physicalDisks.map do |result|
      [result.vsanUuid, result.disk.deviceName]
    end]
    disks.each do |disk|
      disk['deviceName'] = physicalDisks[disk['uuid']]
    end
    return disks
  end

  def _host_info host
    conn = host._connection
    pc = conn.propertyCollector
    prop_names = [
      'name',
      'configManager.vsanSystem',
      'configManager.vsanInternalSystem',
      'config.product',
      'configManager.networkSystem',
      'runtime.inMaintenanceMode',
    ]
    host_props = @basic['hosts_props'][host]
    if host_props && prop_names.all?{|x| host_props.keys.member?(x)}
      # We already have everything
    else
      hosts_props = pc.collectMultiple([host], *prop_names)
      host_props = hosts_props[host]
    end
    netSys = host_props['configManager.networkSystem']
    vsan = host_props['configManager.vsanSystem']
    config = vsan.config
    out = {
      'host_props' => host_props,
      'vsan.config' => config,
    }
    if !config.enabled
      return out
    end

    out['vsanHostStatus'] = vsan.QueryHostStatus()

    vsanIntSys = host_props['configManager.vsanInternalSystem']
    decom_state = vsanIntSys.query_cmmds([
      {:type => 'NODE_DECOM_STATE', :uuid => config.clusterInfo.nodeUuid}
    ])
    if decom_state &&
      decom_state[0] &&
      decom_state[0]['content']['decomState'] == 6
      # Decommission staus: 6 means evacuated
      #                     0 means not evacuated
      host_props['rvc_is_nodedecom'] = true
    else
      host_props['rvc_is_nodedecom'] = false
    end

    out['vmknics'], = netSys.collect 'networkConfig.vnic'

    out
  end

  def _cluster_config_info
    out = {}
    lock = Mutex.new
    hosts_props = @basic['hosts_props']
    @basic['connected_hosts'].map do |host|
      Thread.new do
        conn = host._connection
        c1 = conn.spawn_additional_connection
        host2 = host.dup_on_conn(c1)
        lock.synchronize do
          puts "#{Time.now}: Fetching host info from #{hosts_props[host]['name']} (may take a moment) ..."
        end
        begin
          Timeout.timeout(120) do
            info = _host_info host2
            lock.synchronize do
              out[host] = info
            end
          end
        rescue Exception => ex
          lock.synchronize do
            puts "#{Time.now}: Failed to gather from #{hosts_props[host]['name']}: #{ex.class}: #{ex.message}"
          end
        end
      end
    end.each{|t| t.join}
    out
  end

  def cluster_config_info
    @cluster_config_info ||= _cluster_config_info
  end

end
VsanModel = RVC::VsanModel

opts :lldpnetmap do
  summary "Gather LLDP mapping information from a set of hosts"
  arg :hosts_and_clusters, nil, :lookup => [VIM::HostSystem, VIM::ClusterComputeResource], :multi => true
end

def lldpnetmap hosts_and_clusters, opts = {}
  conn = hosts_and_clusters.first._connection
  hosts = hosts_and_clusters.select{|x| x.is_a?(VIM::HostSystem)}
  pc = conn.propertyCollector
  model = VsanModel.new(
    hosts_and_clusters,
    [],
    :allow_multiple_clusters => true
  )
  hosts += model.basic['hosts']
  hosts = hosts.uniq
  _run_with_rev(conn, "dev") do
    hosts_props = pc.collectMultiple(hosts,
      'name',
      'runtime.connectionState',
      'configManager.vsanSystem',
      'configManager.vsanInternalSystem'
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

    puts "#{Time.now}: This operation will take 30-60 seconds ..."
    hosts_props.map do |host, props|
      Thread.new do
        begin
          vsanIntSys = props['configManager.vsanInternalSystem']
          c1 = conn.spawn_additional_connection
          vsanIntSys = vsanIntSys.dup_on_conn(c1)
          res = vsanIntSys.QueryVsanStatistics(:labels => ['lldpnetmap'])
          res = JSON.parse(res)
          hosts_props[host]['lldpnetmap'] = res['lldpnetmap'] || {}
        rescue Exception => ex
          puts "Failed to gather lldpnetmap from #{props['name']}: #{ex.class}: #{ex.message}"
          hosts_props.delete(host)
        end
      end
    end.each{|t| t.join}

    t = Terminal::Table.new()
    t << ['Host', 'LLDP info']
    t.add_separator
    hosts_props.each do |host, props|
      t << [
        props['name'],
        props['lldpnetmap'].map do |switch, pnics|
          "#{switch}: #{pnics.join(',')}"
        end.join("\n")
      ]
    end
    puts t
  end
end

opts :check_limits do
  summary "Gathers (and checks) counters against limits"
  arg :hosts_and_clusters, nil, :lookup => [VIM::HostSystem, VIM::ClusterComputeResource], :multi => true
end

def check_limits hosts_and_clusters, opts = {}
  conn = hosts_and_clusters.first._connection
  pc = conn.propertyCollector
  _run_with_rev(conn, "dev") do
    model = VsanModel.new(
      hosts_and_clusters,
      [],
      :allow_multiple_clusters => true
    )
    hosts = model.basic['connected_hosts']
    hosts_props = model.basic['hosts_props']

    all_disks = model.query_limits

    # hosts_props.each do |host, props|
      # puts "#{Time.now}: Host #{props['name']}: #{props['profiling']}"
    # end

    t = Terminal::Table.new()
    t << ['Host', 'RDT', 'Disks']
    t.add_separator
    hosts_props.each do |host, props|
      rdt = props['rdtglobal'] || {}
      lsomnode = props['lsom.node'] || {}
      lsomdisks = props['lsom.disks'] || {}
      dom = props['dom'] || {}
      t << [
        props['name'],
        [
          "Assocs: #{rdt['assocCount']}/#{rdt['maxAssocCount']}",
          "Sockets: #{rdt['socketCount']}/#{rdt['maxSocketCount']}",
          "Clients: #{dom['numClients'] || 'N/A'}",
          "Owners: #{dom['numOwners'] || 'N/A'}",
        ].join("\n"),
        ([
          "Components: #{props['components']}/%s" % [
            lsomnode['numMaxComponents'] || 'N/A'
          ],
        ] + (props['disks'] || []).map do |disk|
          if disk['capacity'] > 0
            usage = disk['capacityUsed'] * 100 / disk['capacity']
            usage = "#{usage}%"
          else
            usage = "N/A"
          end
          if !lsomdisks[disk['uuid']].nil?
            maxComp = lsomdisks[disk['uuid']]['info']['maxComp'] || 'N/A'
            numComp = lsomdisks[disk['uuid']]['info']['numComp'] || 'N/A'
          end
          "#{disk['esxcli'].DisplayName}: #{usage} Components: #{numComp}/#{maxComp}"
        end).join("\n"),
      ]
    end
    puts t
  end
end

opts :object_reconfigure do
  summary "Reconfigure a VSAN object"
  arg :cluster, "Cluster on which to execute the reconfig", :lookup => [VIM::HostSystem, VIM::ClusterComputeResource]
  arg :obj_uuid, "Object UUID", :type => :string, :multi => true
  opt :policy, "New policy", :type => :string, :required => true
end

def object_reconfigure cluster_or_host, obj_uuids, opts
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  _run_with_rev(conn, "dev") do
    model = VsanModel.new([cluster_or_host])
    connected_hosts = model.basic['connected_hosts']
    hosts_props = model.basic['hosts_props']
    host = connected_hosts.first
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']

    obj_uuids.each do |uuid|
      puts "Reconfiguring '#{uuid}' to #{opts[:policy]}"
      puts vsanIntSys.ReconfigureDomObject(
        :uuid => uuid,
        :policy => opts[:policy]
      )
    end
  end
  puts "All reconfigs initiated. Synching operation may be happening in the background"
end


opts :obj_status_report do
  summary "Print component status for objects in the cluster."
  arg :cluster_or_hosts, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem], :multi => true
  opt :print_table, "Print a table of object and their status, default all objects",
      :short => 't', :type => :boolean, :default => false
  opt :filter_table, "Filter the obj table based on status displayed in histogram, e.g. 2/3",
      :short => 'f', :type => :string, :default => nil
  opt :print_uuids, "In the table, print object UUIDs instead of vmdk and vm paths",
      :short => 'u', :type => :boolean, :default => false
  opt :ignore_node_uuid, "Estimate the status of objects if all comps on a given host were healthy.",
      :short => 'i', :type => :string, :default => nil
end

def obj_status_report cluster_or_hosts, opts
  conn = cluster_or_hosts.first._connection
  pc = conn.propertyCollector

  hasClusters = cluster_or_hosts.any?{|x| x.is_a?(RbVmomi::VIM::ClusterComputeResource)}
  if cluster_or_hosts.length > 1 && hasClusters
    err "Passing in multiple clusters is not supported"
  end

  _run_with_rev(conn, "dev") do
    model = VsanModel.new(cluster_or_hosts)
    info = model.basic
    hostUuidMap = info['hostUuidMap']
    hosts = info['hosts']
    hosts_props = info['hosts_props']
    host = model.get_first_enabled_host
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']

    entries = nil

    ds = model.get_vsan_ds
    vmsProps = model.get_vsan_vms
    vms = vmsProps.keys
    objects = model.get_cmmds_dom_objects(
      :perform_analysis => true,
      :ignore_node_uuid => opts[:ignore_node_uuid]
    )

    maxObjectVersion = 4
    objectVersions = (0..maxObjectVersion).to_a
    # The object version of v1 objects is 0 in VSAN.
    objectVersions.delete(1)
    versionCounts = nil
    product = hosts_props[host]['config.product']
    if product.version >= '6.0.0'
      puts "#{Time.now}: Querying all object versions in the system ..."
      begin
        versionCounts = Hash[objectVersions.map do |version|
          res = vsanIntSys.QueryVsanObjectUuidsByFilter(:version => version)
          [version, res.length]
        end]
      rescue Exception => ex
        puts "#{Time.now}: Warning: Version information not available:"
        puts "  #{ex.message}"
      end
    end

    #pp liveDisks
    #puts "%d comps total" % liveComps.length

    puts "#{Time.now}: Got all the info, computing table ..."

    results = {}
    orphanRes = {}
    totalObjects = objects.length
    totalOrphans = 0

    objects = objects.select do |obj|
      health = "OK"
      if obj['rvc_num_healthy'] != obj['comps'].length
        if obj['hasLiveness']
          health = "Reduced"
        else
          health = "Unavailable"
        end
      end
      status = [obj['rvc_num_healthy'], obj['comps'].length, health]

      if obj['isOrphan']
        # All absent components are orphaned.  Consider the object orphaned.
        totalOrphans += 1
        orphanRes[status] ||= 0
        orphanRes[status] += 1
      else
        results[status] ||= 0
        results[status] += 1
      end

      if opts[:filter_table]
        ("%d/%d" % status) == opts[:filter_table]
      else
        true
      end
    end
    obj_uuids = objects.map{|x| x['uuid']}
    objectUuidMap = Hash[objects.map{|x| [x['uuid'], x]}]

    vmToObjMap = _compute_vm_to_obj_map(vms, vmsProps, obj_uuids)

    def printObjStatusHist results
      t = Terminal::Table.new()
      t << [
        'Num Healthy Comps / Total Num Comps',
        'Num objects with such status',
      ]
      t.add_separator

      results.each do |key,val|
        t << [
          "%d/%d (%s)" % key,
          " %d" % val,
        ]
      end
      puts t
    end

    puts ""
    puts "Histogram of component health for non-orphaned objects"
    puts ""
    printObjStatusHist(results)
    puts "Total non-orphans: %d" % (totalObjects - totalOrphans)
    puts ""
    puts ""
    puts "Histogram of component health for possibly orphaned objects"
    puts ""
    printObjStatusHist(orphanRes)
    puts "Total orphans: %d" % totalOrphans
    puts ""
    if versionCounts
      objectVersions.each do |version|
        puts "Total v%s objects: %d" % [_marshal_vsan_version(version),
          versionCounts[version]]
      end
    end

    if opts[:print_table] || opts[:filter_table]
      t = Terminal::Table.new()
      t << [
        'VM/Object',
        'objects',
        'num healthy / total comps',
      ]
      t.add_separator
      bytesToSyncGrandTotal = 0
      objGrandTotal = 0
      vmToObjMap.each do |vm, vm_obj_uuids|
        vmProps = vmsProps[vm]
        objs = vm_obj_uuids.keys.map{|x| objectUuidMap[x]}
        t << [
          vmProps['name'],
          objs.length,
          "",
        ]
        objs.each do |obj|
          if opts[:print_uuids]
            objName = obj['uuid']
          else
            objName = (vm_obj_uuids[obj['uuid']] || obj['uuid'])
          end

          if obj['isOrphan']
            orphanStr = "*"
          elsif obj['isOrphanCandidate']
            orphanStr = "-"
          else
            orphanStr = ""
          end

          t << [
            "   %s" % objName,
            '',
            "%d/%d%s" % [obj['rvc_num_healthy'], obj['comps'].length, orphanStr],
          ]
          objects.delete(obj)
        end
      end

      # Okay, now print the remaining UUIDs which didn't map to any VM.
      if objects.length > 0
        if vmToObjMap.length > 0
          t.add_separator
        end
        t << [
          "Unassociated objects",
          '',
          '',
        ]
      end
      objects.each do |obj|
        if obj['isOrphan']
          orphanStr = "*"
        elsif obj['isOrphanCandidate']
          orphanStr = "-"
        else
          orphanStr = ""
        end

        t << [
          "   %s" % obj['uuid'],
          '',
          "%d/%d%s" % [obj['rvc_num_healthy'], obj['comps'].length, orphanStr],
        ]
      end
      puts t
      puts ""
      puts "+------------------------------------------------------------------+"
      puts "| Legend: * = all unhealthy comps were deleted (disks present)     |"
      puts "|         - = some unhealthy comps deleted, some not or can't tell |"
      puts "|         no symbol = We cannot conclude any comps were deleted    |"
      puts "+------------------------------------------------------------------+"
      puts ""
    end
  end
end


opts :apply_license_to_cluster do
  summary "Apply license to VSAN "
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource
  opt :license_key, "License key to be applied to the cluster", :short => 'k', :type => :string, :required => true
  opt :null_reconfigure, "", :short => 'r', :type => :boolean, :default => true
end

def apply_license_to_cluster cluster, opts
  conn = cluster._connection
  puts "#{cluster.name}: Applying VSAN License on the cluster..."
  licenseManager = conn.serviceContent.licenseManager
  licenseAssignmentManager = licenseManager.licenseAssignmentManager
  assignment = licenseAssignmentManager.UpdateAssignedLicense(
    :entity => cluster._ref,
    :licenseKey => opts[:license_key]
  )
  if opts[:null_reconfigure]
    # Due to races in the cluster assignment mechanism in vSphere 5.5 GA a
    # disks may or may not be auto-claimed as would normally be expected.  Doing
    # a Null-Reconfigure causes the license state to be synchronized correctly and
    # allows auto-claim to work as expected.
    puts "#{cluster.name}: Null-Reconfigure to force auto-claim..."
    spec = VIM::ClusterConfigSpecEx()
    task = cluster.ReconfigureComputeResource_Task(:spec => spec, :modify => true)
    progress([task])
    childtasks = task.child_tasks
    if childtasks && childtasks.length > 0
      progress(childtasks)
    end
  end
end

#opts :support_information do
#  summary "Print VSAN info about a datacenter or a cluster"
#  arg :dc_or_cluster, nil, :lookup => VIM::Datacenter
#end

opts :support_information do
  summary "Command to collect vsan support information"
  arg :dc_or_clust_conn, nil, :lookup => [RbVmomi::VIM, VIM::Datacenter, VIM::ClusterComputeResource]
  opt :skip_hostvm_info, "Skip collecting host and vm information in VSAN cluster", :type => :boolean
end


def support_information dc_or_clust_or_conn, opts = {}
  puts "VMware virtual center #{dc_or_clust_or_conn._connection.serviceContent.about.instanceUuid}\n"
  time1 = Time.now.utc
  if  dc_or_clust_or_conn.is_a?(RbVmomi::VIM)
    puts  "*** command> vsan.support_information\n"
  else
    puts "*** command> vsan.support_information #{dc_or_clust_or_conn.name}\n"
  end
  if dc_or_clust_or_conn.is_a?(RbVmomi::VIM)
    vim = dc_or_clust_or_conn;
    _get_vimConn_supportinfo vim, opts[:skip_hostvm_info]
  elsif dc_or_clust_or_conn.is_a?(VIM::Datacenter)
    datacenter = dc_or_clust_or_conn
    _get_datacenter_supportinfo datacenter, opts[:skip_hostvm_info]
  else
    cluster = dc_or_clust_or_conn
    _get_cluster_supportinfo cluster, opts[:skip_hostvm_info]
  end
  time2 = Time.now.utc
  puts "Total time taken - #{time2-time1} seconds"

end

def _get_vimConn_supportinfo vim, skipHostAndVm
  begin
    rootfolder = vim.serviceContent.rootFolder
    childEntities = rootfolder.childEntity
    _get_child_entities childEntities, skipHostAndVm
  rescue Exception => e
    puts e.message
  end

end


def _get_datacenter_supportinfo datacenter, skipHostAndVm
  begin
    dc_name = datacenter.name
    puts "************* BEGIN Support info for datacenter #{dc_name} *************"
    hostfolder = datacenter.hostFolder
    childEntities = hostfolder.childEntity
    _get_child_entities childEntities, skipHostAndVm
  rescue Exception => e
    puts "datacenter #{datacenter.name} hit an error."
    puts e.message
  ensure
    puts "************* END Support info for datacenter #{dc_name} *************\n\n\n"
  end

end

def _get_child_entities childEntities, skipHostAndVm

    childEntities.each do |child|
      begin
        if child.is_a?(VIM::ClusterComputeResource)
          cluster_name = child.name
          puts "************* BEGIN Support info for cluster #{cluster_name} *************\n"
          _get_cluster_supportinfo child, skipHostAndVm
          puts "\n************* END Support info for cluster #{cluster_name} *************\n\n"
        elsif child.is_a?(VIM::Folder)
          childEntity = child.childEntity
          _get_child_entities childEntity, skipHostAndVm
        elsif child.is_a?(VIM::Datacenter)
          _get_datacenter_supportinfo child, skipHostAndVm
        else
          puts "Ignoring object #{child.name}"
        end

      rescue Exception => e
        puts " #{child.name} hit an error."
        puts e.message
        next
      end
    end
end


def _get_cluster_supportinfo cluster, skipHostAndVm
  conn = cluster._connection
  pc = conn.serviceContent.propertyCollector

  cluster_name = cluster.name
  puts "\n*** command>vsan.cluster_info #{cluster_name}"
  clusters = []
  #clusters = Array.new(1) {Array.new}
  clusters<<cluster
  opts = {}
  opts[:interval] = 20
  begin
    cluster_info clusters
  rescue Exception => e
    puts "\n cluster_info #{cluster_name} hit an error}"
    puts e.message
  end

  hosts = cluster.host
  hosts_props = pc.collectMultiple(hosts, 'vm', 'name')

  if !skipHostAndVm
    hosts.each do |host|
      begin
        host_name = hosts_props[host]['name']

        begin
          puts "\n*** command>vsan.host_info #{host_name}"
          host_info host
        rescue Exception => e
          puts "\n vsan,host_info #{host_name} hit an error"
          puts e.message
        end

        vms = hosts_props[host]['vm']

        begin
          puts "\n*** command>vsan.vm_object_info "
          if vms.length > 0
            vm_object_info vms, opts
          else
            puts "couldn't find any vms on host #{host_name}"
          end
        rescue Exception => e
          puts "\n vm_object_info hit an error on host #{host_name}"
          puts e.message
        end

        # Not including the command vsan.vm_perf_stats for this release,
        # as this command is slow.
        #begin
        #  puts "\n*** command>vsan.vm_perf_stats "
        #  if vms.length > 0
        #    vm_perf_stats vms, opts
        #  else
        #    puts "couldn't find any vms on host #{host_name}"
        #  end
        #rescue Exception => e
        #  puts "\n vm_perf_stats hit an error on host #{host_name}."
        #  puts e.message
        #end

      rescue Exception => e
        puts "\n host #{host_name} hit an error. "
        puts e.message
        next
      end
    end
  end

  begin
    puts "\n*** command>vsan.disks_info"
    if hosts.length > 0
    	disks_info hosts
    else
        puts "Couldn't find any connected hosts on cluster #{cluster_name}\n"
    end
  rescue Exception => e
    puts "\n vsan.disks_info hit an error on cluster #{cluster_name}."
    puts e.message
  end

  begin
    puts "\n*** command>vsan.disks_stats "
    if hosts.length > 0
      disks_stats hosts
    else
      puts "Couldn't find any connected hosts on cluster #{cluster_name}\n"
    end
  rescue Exception => e
    puts "\n vsan.disks_stats hit an error on cluster #{cluster_name}."
    puts e.message
  end

  begin
    puts "\n*** command>vsan.check_limits #{cluster_name}"
    check_limits clusters
  rescue Exception => e
    puts "\n vsan.check_limits #{cluster_name} hit an error."
    puts e.message
  end

  begin
    puts "\n*** command>vsan.check_state #{cluster_name}"
    check_state cluster, opts
  rescue Exception => e
    puts "\n*** vsan.check_State #{cluster_name} hit an error."
    puts e.message
  end

  begin
    puts "\n*** command>vsan.lldpnetmap #{cluster_name}"
    lldpnetmap clusters
  rescue Exception => e
    puts "\n vsan.lldpnetmap #{cluster_name} hit an error."
    puts e.message
  end

  begin
    puts "\n*** command>vsan.obj_status_report #{cluster_name}"
    obj_status_report [cluster], opts
  rescue Exception => e
    puts "\n vsan.obj_status_report #{cluster_name} hit an error."
    puts e.message
  end

  begin
    puts  "\n*** command>vsan.resync_dashboard #{cluster_name}"
    resync_dashboard cluster, opts
  rescue Exception => e
    puts "\n vsan.resync_dashboard #{cluster_name} hit an error."
    puts e.message
  end

  if !skipHostAndVm
    begin
      disk_uuids = []
      puts "\n*** command>vsan.disk_object_info #{cluster_name}, disk_uuids"
      host_vsan_uuids, hosts_props, vsan_disk_uuids =  _vsan_cluster_disks_info(cluster)
      vsan_disk_uuids.values.each do |vsan_disk_uuid|
        disk_uuids << vsan_disk_uuid.Device
      end
      disk_object_info cluster, disk_uuids, opts
    rescue Exception => e
      puts "\n vsan.disk_object_info #{cluster_name}, disk_uuids hit an error"
      puts e.message
    end
  end
end


opts :check_state do
  summary "Checks state of VMs and VSAN objects"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :refresh_state, "Not just check state, but also refresh", :type => :boolean
  opt :reregister_vms,
      "Not just check for vms with VC/hostd/vmx out of sync but also " \
      "fix them by un-registering and re-registering them",
      :type => :boolean
  opt :force, "Force to re-register vms, without confirmation", :type => :boolean
end

def check_state cluster_or_host, opts
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  _run_with_rev(conn, "dev") do
    model = VsanModel.new([cluster_or_host])
    hosts_props = model.basic['hosts_props']

    host = model.get_first_enabled_host
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

    ds_list = host.datastore
    ds_props = pc.collectMultiple(ds_list, 'name', 'summary.type')
    ds = ds_props.select{|k, x| x['summary.type'] == "vsan"}.keys.first

    vms = ds.vm
    vms_props = pc.collectMultiple(vms, 'name', 'runtime.connectionState')

    puts "#{Time.now}: Step 1: Check for inaccessible VSAN objects"

    statusses = vsanIntSys.query_cmmds([{:type => 'CONFIG_STATUS'}])
    bad = statusses.select do |x|
      state = _assessAvailabilityByStatus(x['content']['state'])
      !state['DATA_AVAILABLE'] || !state['QUORUM']
    end

    if !opts[:refresh_state]
      puts "Detected #{bad.length} objects to be inaccessible"
      bad.each do |x|
        uuid = x['uuid']
        hostname = hostUuidMap[x['owner']]
        puts "Detected #{uuid} on #{hostname} to be inaccessible"
      end
    else
      bad.group_by{|x| hostUuidMap[x['owner']]}.each do |hostname, badOnHost|
        owner = hosts_props.select{|k,v| v['name'] == hostname}.keys.first
        owner_props = hosts_props[owner]
        owner_vsanIntSys = owner_props['configManager.vsanInternalSystem']
        badOnHost.each do |x|
          uuid = x['uuid']
          puts "Detected #{uuid} to be inaccessible, refreshing state"
        end
        if badOnHost.length > 0
          badUuids = badOnHost.map{|x| x['uuid']}
          owner_vsanIntSys.AbdicateDomOwnership(:uuids => badUuids)
        end
      end
      puts ""

      sleep 5
      puts "#{Time.now}: Step 1b: Check for inaccessible VSAN objects, again"
      statusses = vsanIntSys.query_cmmds([{:type => 'CONFIG_STATUS'}])
      bad = statusses.select do |x|
        state = _assessAvailabilityByStatus(x['content']['state'])
        !state['DATA_AVAILABLE'] || !state['QUORUM']
      end
      bad.each do |x|
        puts "Detected #{x['uuid']} is still inaccessible"
      end
    end
    puts ""

    puts "#{Time.now}: Step 2: Check for invalid/inaccessible VMs"
    invalid_vms = vms_props.select do |k,v|
      ['invalid', 'inaccessible', 'orphaned'].member?(v['runtime.connectionState'])
    end.keys
    tasks = []
    invalid_vms.each do |vm|
      vm_props = vms_props[vm]
      vm_state = vm_props['runtime.connectionState']
      if !opts[:refresh_state]
        puts "Detected VM '#{vm_props['name']}' as being '#{vm_state}'"
      else
        puts "Detected VM '#{vm_props['name']}' as being '#{vm_state}', reloading ..."
        begin
          if vm_state == 'orphaned'
            path = vm.summary.config.vmPathName
            tasks << vm.reloadVirtualMachineFromPath_Task(
              :configurationPath => path
            )
          else
            vm.Reload
            vm.Reload
          end
        rescue Exception => ex
          puts "#{ex.class}: #{ex.message}"
        end
      end
    end
    tasks = tasks.compact
    if tasks.length > 0
      progress(tasks)
    end
    puts ""

    if opts[:refresh_state]
      puts "#{Time.now}: Step 2b: Check for invalid/inaccessible VMs again"
      vms_props = pc.collectMultiple(vms, 'name', 'runtime.connectionState')
      invalid_vms = vms_props.select do |k,v|
        ['invalid', 'inaccessible', 'orphaned'].member?(v['runtime.connectionState'])
      end.keys
      invalid_vms.each do |vm|
        vm_props = vms_props[vm]
        vm_state = vm_props['runtime.connectionState']
        puts "Detected VM '#{vm_props['name']}' as still '#{vm_state}'"
      end
      puts ""
    end

    puts "#{Time.now}: Step 3: Check for VMs for which VC/hostd/vmx" \
         " are out of sync"
    inconsistent_vms = find_inconsistent_vms(cluster_or_host)
    if opts[:reregister_vms] and not inconsistent_vms.empty?
      proceed = opts[:force] || _questionnaire(
        "You have chosen to fix these VMs. This involves re-registering" \
        " the VM which will cause loss of some of the management state of"\
        " this VM (for eg. storage policy, permissions, tags," \
        " scheduled tasks, etc. but NO data loss). Do you want to" \
        " continue [Y/N] ?",
        ['y', 'n'],
        'y'
      )
      if proceed
         puts "Attempting to fix these vms..."
         fix_inconsistent_vms(inconsistent_vms)
      end
    end
    puts ""

  end
end


opts :reapply_vsan_vmknic_config do
  summary "Unbinds and rebinds VSAN to its vmknics"
  arg :host, nil, :lookup => [VIM::HostSystem], :multi => true
  opt :vmknic, "Refresh a specific vmknic. default is all vmknics", :type => :string
  opt :dry_run, "Do a dry run: Show what changes would be made", :type => :boolean
end

def reapply_vsan_vmknic_config hosts, opts
  hosts.each do |host|
    hostname = host.name
    net = host.esxcli.vsan.network
    nics = net.list()
    if opts[:vmknic]
      nics = nics.select{|x| x.VmkNicName == opts[:vmknic]}
    end
    keys = {
      :AgentGroupMulticastAddress => :agentmcaddr,
      :AgentGroupMulticastPort => :agentmcport,
      :IPProtocol => nil,
      :InterfaceUUID => nil,
      :MasterGroupMulticastAddress => :mastermcaddr,
      :MasterGroupMulticastPort => :mastermcport,
      :MulticastTTL => :multicastttl,
    }
    puts "Host: #{hostname}"
    if opts[:dry_run]
      nics.each do |nic|
        puts "  Would reapply config of vmknic #{nic.VmkNicName}:"
        keys.keys.each do |key|
          puts "    #{key.to_s}: #{nic.send(key)}"
        end
      end
    else
      nics.each do |nic|
        puts "  Reapplying config of #{nic.VmkNicName}:"
        keys.keys.each do |key|
          puts "    #{key.to_s}: #{nic.send(key)}"
        end
        puts "  Unbinding VSAN from vmknic #{nic.VmkNicName} ..."
        net.ipv4.remove(:interfacename => nic.VmkNicName)
        puts "  Rebinding VSAN to vmknic #{nic.VmkNicName} ..."
        params = {
          :agentmcaddr => nic.AgentGroupMulticastAddress,
          :agentmcport => nic.AgentGroupMulticastPort,
          :interfacename => nic.VmkNicName,
          :mastermcaddr => nic.MasterGroupMulticastAddress,
          :mastermcport => nic.MasterGroupMulticastPort,
          :multicastttl => nic.MulticastTTL,
        }
        #pp params
        net.ipv4.add(params)
      end
    end
  end
end

def _questionnaire2 question, answers, expect_answer
  _questionnaire question, answers, expect_answer
end


opts :recover_spbm do
  summary "SPBM Recovery"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :dry_run, "Don't take any automated actions", :type => :boolean
  opt :force, "Answer all question with 'yes'", :type => :boolean
end

def _adjustProfileForNamespace profile
  profile = profile.dup
  capabilities = {
    'stripeWidth' => 1,
    'proportionalCapacity' => 0,
    'cacheReservation' => 0,
  }
  capabilities.each do |cap, val|
    if profile[cap]
      profile[cap] = val
    end
  end
  profile
end

def _profileWithAllDefaults profile
  profile = profile.dup
  capabilities = {
    'stripeWidth' => 1,
    'proportionalCapacity' => 0,
    'cacheReservation' => 0,
  }
  capabilities.each do |cap, val|
    if !profile[cap]
      profile[cap] = val
    end
  end
  profile
end

def _profileSame?(a, b)
  _profileWithAllDefaults(a) == _profileWithAllDefaults(b)
end


def recover_spbm cluster_or_host, opts
  conn = cluster_or_host._connection
  pc = conn.propertyCollector
  host = cluster_or_host
  entries = []
  hostUuidMap = {}
  startTime = Time.now

  _run_with_rev(conn, "dev") do
  _catch_spbm_resets(conn) do
    vsanIntSys = nil
    puts "#{Time.now}: Fetching Host info"

    model = VsanModel.new(
      [cluster_or_host],
      ['datastore']
    )
    connected_hosts = model.basic['connected_hosts']
    hosts_props = model.basic['hosts_props']
    host = connected_hosts.first
    vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
    vsanSysList = Hash[hosts_props.map do |host, props|
      [props['name'], props['configManager.vsanSystem']]
    end]
    clusterInfos = pc.collectMultiple(vsanSysList.values,
                                      'config.clusterInfo')
    hostUuidMap = Hash[vsanSysList.map do |hostname, sys|
      [clusterInfos[sys]['config.clusterInfo'].nodeUuid, hostname]
    end]

    puts "#{Time.now}: Fetching Datastore info"
    datastores = hosts_props.values.map{|x| x['datastore']}.flatten
    datastores_props = pc.collectMultiple(datastores, 'name', 'summary.type')
    vsanDsList = datastores_props.select do |ds, props|
      props['summary.type'] == "vsan"
    end.keys
    if vsanDsList.length > 1
      err "Two VSAN datastores found, can't handle that"
    end
    vsanDs = vsanDsList[0]

    puts "#{Time.now}: Fetching VM properties"
    vms = vsanDs.vm
    vms_props = pc.collectMultiple(vms, 'name', 'config.hardware.device', 'layoutEx.file')

    puts "#{Time.now}: Fetching policies used on VSAN from CMMDS"
    entries = vsanIntSys.query_cmmds([{
      :type => "POLICY",
    }])

    policies = entries.map{|x| x['content']}.uniq

    puts "#{Time.now}: Fetching SPBM profiles"
    pbm = conn.pbm
    pm = pbm.serviceContent.profileManager
    profileIds = pm.PbmQueryProfile(
      :resourceType => {:resourceType => "STORAGE"},
      :profileCategory => "REQUIREMENT"
    )
    if profileIds.length > 0
      profiles = pm.PbmRetrieveContent(:profileIds => profileIds)
    else
      profiles = []
    end
    profilesMap = Hash[profiles.map do |x|
      ["#{x.profileId.uniqueId}-gen#{x.generationId}", x]
    end]

    puts "#{Time.now}: Fetching VM <-> SPBM profile association"
    vms_entities = vms.map do |vm|
      vm.all_pbmobjref(:vms_props => vms_props)
    end.flatten.map{|x| x.dynamicProperty = []; x}
    associatedProfiles = pm.PbmQueryAssociatedProfiles(
      :entities => vms_entities
    )
    associatedEntities = associatedProfiles.map{|x| x.object}.uniq
    puts "#{Time.now}: Computing which VMs do not have a SPBM Profile ..."

    nonAssociatedEntities = vms_entities - associatedEntities

    vmsMap = Hash[vms.map{|x| [x._ref, x]}]
    nonAssociatedVms = {}
    nonAssociatedEntities.map do |entity|
      vm = vmsMap[entity.key.split(":").first]
      nonAssociatedVms[vm] ||= []
      nonAssociatedVms[vm] << [entity.objectType, entity.key]
    end
    puts "#{Time.now}: Fetching additional info about some VMs"

    vms_props2 = pc.collectMultiple(vms, 'summary.config.vmPathName')

    puts "#{Time.now}: Got all info, computing after %.2f sec" % [
      Time.now - startTime
    ]

    policies.each do |policy|
      policy['spbmRecoveryCandidate'] = false
      policy['spbmProfile'] = nil
      if policy['spbmProfileId']
        name = "%s-gen%s" % [
          policy['spbmProfileId'],
          policy['spbmProfileGenerationNumber'],
        ]
        policy['spbmName'] = name
        policy['spbmProfile'] = profilesMap[name]
        recoveredProfile = nil
        if !policy['spbmProfile']
          recoveredProfile = profiles.find{|x| x.name == name}
        end
        if policy['spbmProfile']
          name = policy['spbmProfile'].name
          policy['spbmName'] = name
          name = "Existing SPBM Profile:\n#{name}"
        elsif recoveredProfile
          policy['spbmProfile'] = recoveredProfile
          name = "Recovered SPBM Profile:\n#{name}"
        else
          policy['spbmRecoveryCandidate'] = true
          profile = profiles.find do |profile|
            profile.profileId.uniqueId == policy['spbmProfileId'] &&
            profile.generationId > policy['spbmProfileGenerationNumber']
          end
          # XXX: We should check if there is a profile that matches
          # one we recovered
          if profile
            name = policy['spbmProfile'].name
            name = "Old generation of SPBM Profile:\n#{name}"
          else
            name = "Unknown SPBM Profile. UUID:\n#{name}"
          end
        end
      else
        name = "Not managed by SPBM"
        policy['spbmName'] = name
      end
      propCap = policy['proportionalCapacity']
      if propCap && propCap.is_a?(Array) && propCap.length == 2
        policy['proportionalCapacity'] = policy['proportionalCapacity'][0]
      end

      policy['spbmDescr'] = name
    end
    entriesMap = Hash[entries.map{|x| [x['uuid'], x]}]

    nonAssociatedEntities = []
    nonAssociatedVms.each do |vm, entities|
      if entities.any?{|x| x == ["virtualMachine", vm._ref]}
        vmxPath = vms_props2[vm]['summary.config.vmPathName']
        if vmxPath =~ /^\[([^\]]*)\] ([^\/]*)\//
          nsUuid = $2
          entry = entriesMap[nsUuid]
          if entry && entry['content']['spbmProfileId']
            # This is a candidate
            nonAssociatedEntities << {
              :objUuid => nsUuid,
              :type => "virtualMachine",
              :key => vm._ref,
              :entry => entry,
              :vm => vm,
              :label => "VM Home",
            }
          end
        end
      end
      devices = vms_props[vm]['config.hardware.device']
      disks = devices.select{|x| x.is_a?(VIM::VirtualDisk)}
      disks.each do |disk|
        key = "#{vm._ref}:#{disk.key}"
        if entities.any?{|x| x == ["virtualDiskId", key]}
          objUuid = disk.backing.backingObjectId
          if objUuid
            entry = entriesMap[objUuid]
            if entry && entry['content']['spbmProfileId']
              # This is a candidate
              nonAssociatedEntities << {
                :objUuid => objUuid,
                :type => "virtualDiskId",
                :key => key,
                :entry => entry,
                :vm => vm,
                :label => disk.deviceInfo.label,
              }
            end
          end
        end
      end
    end
    nonAssociatedEntities.each do |entity|
      policy = policies.find do |policy|
        match = true
        ['spbmProfileId', 'spbmProfileGenerationNumber'].each do |k|
          match = match && policy[k] == entity[:entry]['content'][k]
        end
        match
      end
      entity[:policy] = policy
    end

    candidates = policies.select{|p| p['spbmRecoveryCandidate'] == true}

    puts "#{Time.now}: Done computing"

    puts "SPBM Profiles used by VSAN:"
    t = Terminal::Table.new()
    t << ['SPBM ID', 'policy']
    policies.each do |policy|
      t.add_separator
      t << [
        policy['spbmDescr'],
        policy.select{|k,v| k !~ /spbm/}.map{|k,v| "#{k}: #{v}"}.join("\n")
      ]
    end
    puts t
    puts ""

    if candidates.length > 0
      names = candidates.map{|x| x['spbmName']}.uniq
      names.each do |name|
        matches = candidates.select{|x| x['spbmName'] == name}
        if matches.length == 2
          a, b = matches
          nsA, nsB = matches.map{|x| _adjustProfileForNamespace(x)}
          if _profileSame?(a, nsB)
            # a is the namespace equivalent of b
            a['skip'] = true
          elsif _profileSame?(b, nsA)
            # b is the namespace equivalent of a
            b['skip'] = true
          end
        end
      end
      candidates = candidates.select{|x| !x['skip']}
    end
    if candidates.length > 0
      puts "Recreate missing SPBM Profiles using following RVC commands:"
      candidates.each do |policy|
        rules = policy.select{|k,v| k !~ /spbm/ && k != "objectVersion"}
        s = rules.map{|k,v| "--rule VSAN.#{k}=#{v}"}.join(" ")
        puts "spbm.profile_create #{s} #{policy['spbmName']}"
      end
      puts ""
      createNow = opts[:force]
      if !opts[:dry_run] && !opts[:force]
        createNow = _questionnaire2(
          "Do you want to create SPBM Profiles now? [Y/N]",
          ['y', 'n'],
          'y'
        )
      end
      if createNow
        candidates.each do |policy|
          rules = policy.select{|k,v| k !~ /spbm/ && k != "objectVersion"}
          rulesStrings = rules.map{|k,v| "VSAN.#{k}=#{v}"}
          s = rules.map{|k,v| "--rule VSAN.#{k}=#{v}"}.join(" ")
          puts "Running: spbm.profile_create #{s} #{policy['spbmName']}"
          shell.cmds.spbm.profile_create(
            policy['spbmName'],
            :rule => rulesStrings
          )
        end
        puts ""
        puts "Please rerun the command to fix up any missing VM <-> SPBM Profile associations"
        return
      end
    end

    if nonAssociatedEntities.length > 0
      puts "Following missing VM <-> SPBM Profile associations were found:"
      t = Terminal::Table.new()
      t << ['Entity', 'VM', 'Profile']
      t.add_separator
      nonAssociatedEntities.each do |entity|
        #puts "'%s' of VM '%s' should be associated with profile '%s' but isn't." % [
        t << [
          entity[:label],
          vms_props[entity[:vm]]['name'],
          entity[:policy]['spbmName'],
        ]
      end
      puts t

      patchNow = opts[:force]
      if !opts[:dry_run] && !opts[:force]
        patchNow = _questionnaire2(
          "Do you want to create missing associations now? [Y/N]",
          ['y', 'n'],
          'y'
        )
      end
      if patchNow
        entities = nonAssociatedEntities.select{|x| x[:policy]['spbmProfile']}
        tasks = []
        entities.group_by{|x| x[:vm]}.each do |vm, vmEntities|
          puts "#{Time.now}: Fixing association of VM '%s'" % [
            vms_props[vm]['name'],
          ]
          spec = {}
          vmEntities.each do |entity|
            profile = entity[:policy]['spbmProfile']
            profileSpec = [VIM::VirtualMachineDefinedProfileSpec(
              :profileId => profile.profileId.uniqueId
            )]
            if entity[:type] == "virtualMachine"
              spec[:vmProfile] = profileSpec
            end
            if entity[:type] == "virtualDiskId"
              disks = vm.disks
              disk = disks.find{|x| "#{vm._ref}:#{x.key}" == entity[:key]}
              if disk
                spec[:deviceChange] ||= []
                spec[:deviceChange] << {
                  :operation => :edit,
                  :device => disk,
                  :profile => profileSpec,
                }
              end
            end
          end
          tasks << vm.ReconfigVM_Task(:spec => spec)
          if tasks.length >= 10
            progress(tasks)
            tasks = []
          end
        end # entities.group_by{}.each
        if tasks.length > 0
          progress(tasks)
        end
      end # patchNow
    end
  end
  end
end


opts :vmdk_stats do
  summary "Print read cache and capacity stats for vmdks.\n" \
          "Disk Capacity (GB):\n"                            \
          "Disk Size: Size of the vmdk\n"                    \
          "Used Capacity: MD capacity used by this vmdk\n"   \
          "Data Size: Size of data on this vmdk\n"           \
          "Read Cache (GB):\n"                               \
          "Used: RC used by this vmdk\n"                     \
          "Reserved: RC reserved by this vmdk\n"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  arg :vms, nil, :lookup => VIM::VirtualMachine, :multi => true
end

def vmdk_stats cluster_or_host, vms
  conn = cluster_or_host._connection
  pc = conn.propertyCollector
  puts "#{Time.now}: Fetching general information about cluster"

  model = VsanModel.new([cluster_or_host])
  connected_hosts = model.basic['connected_hosts']
  hosts_props = model.basic['hosts_props']

  host = connected_hosts.first
  vsanIntSys = hosts_props[host]['configManager.vsanInternalSystem']
  vsandisks = vsanIntSys.query_physical_vsan_disks(:props => [
    'uuid',
    'formatVersion',
  ])

  t = Terminal::Table.new()
  t << [nil,
        {:value => 'Disk Capacity (in GB)', :colspan => 3, :alignment => :center},
        {:value => 'Read Cache (in GB)', :colspan => 2, :alignment => :center}]
  t.add_separator
  t << ['Disk Name', 'Disk Size', 'Used Capacity', 'Data Size',
        'Used', 'Reserved']

  puts "#{Time.now}: Fetching general information about VMs"
  vmProps = pc.collectMultiple(
    vms,
    'name', 'config.hardware.device', 'summary.config', 'layoutEx.file',
  )
  vm_obj_uuids = {}
  vms.each do |vm|
    vm_obj_uuids[vm] = _get_vm_obj_uuids(vm, vmProps)
  end
  puts "#{Time.now}: Fetching information about VSAN objects"
  cmmds = vsanIntSys.query_vsan_objects(
            :uuids => vm_obj_uuids.values.map{|x| x.keys}.flatten.compact
          )
  puts "#{Time.now}: Fetching VSAN stats"
  lsomCompStats = {}
  lock = Mutex.new
  connected_hosts.map do |host|
    Thread.new do
      c1 = conn.spawn_additional_connection
      props = hosts_props[host]
      vsanIntSys2 = props['configManager.vsanInternalSystem']
      vsanIntSys3 = vsanIntSys2.dup_on_conn(c1)
      res = vsanIntSys3.query_vsan_statistics(:labels => ['lsom', 'lsom-components'])
      lock.synchronize do
        lsomCompStats.merge!(res['lsom.components'])
      end
    end
  end.each{|t| t.join}

  puts "#{Time.now}: Done fetching info, drawing table"
  compsWithoutStats = []
  total_space = 0
  total_disk = 0
  vm_obj_uuids.each do |vm, disk_info|
    vm_obj_uuids = _get_vm_obj_uuids(vm, vmProps)
    t.add_separator
    t << [vmProps[vm]['name'], nil, nil, nil, nil, nil]
    disk_info.each do |uuid, disk|
      # Skip the namespace object
      if /.vmdk\Z/ !~ disk
        next
      end
      dom_config = cmmds['dom_objects'][uuid]
      if !dom_config
        # XXX: Think this through
        next
      end
      disk_size = dom_config['config']['content']['attributes']['addressSpace']
      used_size = 0
      phys_used_size = 0
      rc_used = 0
      rc_reserved = 0
      dom_components = _components_in_dom_config(
                         dom_config['config']['content']
                       )
      dom_components.each do |component|
        if component['attributes'].has_key?('capacity')
          if component['attributes']['capacity'].is_a?(Array)
            used_size += component['attributes']['capacity'][0]
          else
            used_size += component['attributes']['capacity']
          end
        end
        if component['attributes'].has_key?('readCacheReservation')
          rc_reserved += component['attributes']['readCacheReservation']
        end
        if component['type'] == 'Component'
          compUuid = component['componentUuid']
          diskUuid = component['diskUuid']
          lsomComp = cmmds['lsom_objects'][compUuid]
          if lsomComp['content'].has_key?('physCapacityUsed')
            compPhysUsed = lsomComp['content']['physCapacityUsed']
            # Subtract the per-component metadata overhead of 2MB
            # XXX: Shouldn't be hardcoded
            # 4 MB for v2, 2MB for v1
            vsandisk = vsandisks[diskUuid]
            formatVersion = nil
            if vsandisk
              formatVersion = vsandisk['formatVersion']
            end
            if formatVersion != 0
              compPhysUsed -= 4 * 1024**2
            else
              compPhysUsed -= 2 * 1024**2
            end
            phys_used_size += compPhysUsed
          end

          compRcUsed = nil
          compStats = lsomCompStats[compUuid]
          if compStats
            compRcUsed = compStats['rcStats']['rcSsdUsedBytes']
            rc_used += compRcUsed
          else
            compsWithoutStats << compUuid
          end
        end
        if used_size < phys_used_size
          used_size = phys_used_size
        end
      end
      total_space += used_size
      total_disk += disk_size
      gb = 1024 * 1024 * 1024.0
      disk_size /= gb
      used_size /= gb
      phys_used_size /= gb
      rc_used /= gb
      rc_reserved /= gb
      cols = [
        "%.1f" % [disk_size],
        "%.1f (%.1fx)" % [used_size, used_size / disk_size],
        "%.1f" % [phys_used_size],
        "%.1f" % [rc_used],
        "%.1f" % [rc_reserved],
      ]
      t << ([disk] + cols)
    end
  end
  if compsWithoutStats.length > 0
    puts "#{Time.now}: Warning: No RC stats for #{compsWithoutStats.length} components"
  end
  puts t
  # puts "Total disk space: %.2fTB" % [total_disk / 1024.0**4]
  # puts "Total used space: %.2fTB" % [total_space / 1024.0**4]
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

def _is_v6_compatible conn
  return conn.serviceContent.about.version >= '6.0.0'
end


def _marshal_disk_mapping_error dr
  error = dr.error
  if error.is_a?(VIM::DiskHasPartitions)
    return error.device + " already has partition"
  elsif error.is_a?(VIM::DiskIsLastRemainingNonSSD)
    return error.device + " is the last remaining non-SSD disk"
  elsif error.is_a?(VIM::VsanDiskFault)
    return error.device
  elsif error.is_a?(RbVmomi::VIM::SystemError)
    return error.reason
  elsif error.is_a?(VIM::LocalizedMethodFault)
    return error.localizedMessage
  else
    # XXX, unknown error, this method should be refined if we get more explicitly thrown exceptions.
    return "Unexpected error (#{error.class}: #{error})"
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
    input = $stdin.gets
    input = input ? input.chomp : ""
    answer = answers.find{|a| input.casecmp(a) == 0}
  end while !answer
  return input.casecmp(expect_answer) == 0
end

opts :scrubber_info do
   summary "Print scrubber info about objects on this host or cluster"
   arg :cluster_or_hosts, nil, :lookup => [VIM::HostSystem, VIM::ClusterComputeResource], :multi => true
end

def scrubber_info cluster_or_hosts
  conn = cluster_or_hosts.first._connection
  pc = conn.propertyCollector
  model = VsanModel.new(
    cluster_or_hosts,
    ['vm'],
    :allow_multiple_clusters => true
  )
  hosts = model.basic['connected_hosts']
  hosts_props = model.basic['hosts_props']

  if hosts.empty?
    RVC::Util::err "No host specified to query, stop current operation."
    return
  end

  objstats = {}
  hosts.map do |host|
    Thread.new do
      c1 = conn.spawn_additional_connection
      props = hosts_props[host]
      vsanIntSys2 = props['configManager.vsanInternalSystem']
      vsanIntSys3 = vsanIntSys2.dup_on_conn(c1)
      res = vsanIntSys3.QueryVsanStatistics(:labels => ['scrub-stats'])
      res = rvc_load_json(res)['dom.owners.scrubStats']
      if res != nil && !res.empty?
        res.each do |k, v|
          objstats[k] = v
        end
      end
    end
  end.each{|t| t.join}

  vm_list = []
  host_vm_map = {}
  hosts.each do |host|
    begin
      vms = hosts_props[host]['vm']
      if vms != nil && !vms.empty?
        vm_list += vms
        host_vm_map[host] = vms
      end
    rescue
      puts "\nUnable to get host vms"
    end
  end

  if vm_list.empty?
    RVC::Util::err "No vms found in on the cluster/host, stop current operation."
    return
  end

  vmsProps = pc.collectMultiple(vm_list,
    'name', 'runtime.connectionState',
    'config.hardware.device', 'summary.config', 'layoutEx.file'
  )
  vm_disk_map = {}

  vm_list.each do |vm|
    vm_disk_map[vmsProps[vm]['name']] = _get_vm_obj_uuids(vm, vmsProps)
  end

  host_vm_map.each do |host, vms|
    ht = Terminal::Table.new()
    ht << ['Host', hosts_props[host]['name']]
    t = Terminal::Table.new()
    t << ['Obj Name', 'Total object Size', 'Scrubbed',
          'Media errors detected', 'Media errors recovered']
    t.add_separator
    vms.each do |vm|
      t << ["VM: %s" % vmsProps[vm]['name'], nil, nil, nil, nil]
      vm_disk_map[vmsProps[vm]['name']].each do |disk_uuid, disk_name|
        scrubStats = objstats[disk_uuid]
        if scrubStats == nil || scrubStats.empty?
          next
        end
        t << ["  %s" % disk_name,
              "%.1f GB" % [scrubStats['totalObjSize'] / 1024.0**3],
              "%.1f GB" % [scrubStats['totalBytesScrubbed'] / 1024.0**3],
              scrubStats['numErrorsDetected'],
              scrubStats['numErrorsRecovered']]
      end
    end
    puts ht
    puts t
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
    'configManager.vsanInternalSystem',
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


opts :host_claim_disks_differently do
  summary "Tags all devices of a certain model as certain type of device"
  arg :hosts, nil, :lookup => [VIM::HostSystem], :multi => true
  opt :model, "Model of disk to be claimed as capacity tier", :type => :string, :multi => true
  opt :disk, "Disk name to be claimed as capacity tier", :type => :string, :multi => true
  opt :claim_type, "Claim types: capacity_flash, hdd, ssd", :type => :string, :required => true
end

def host_claim_disks_differently hosts, opts = {}
  valid_types = ['capacity_flash', 'hdd', 'ssd']
  if !valid_types.member?(opts[:claim_type])
    err "claim-type must be one of #{valid_types}"
  end
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
      modelMatch = opts[:model].any? do |model|
        disk.disk.model =~ /#{model}/
      end
      nameMatch = opts[:disk].any? do |diskname|
        disk.disk.canonicalName == diskname
      end
      modelMatch || nameMatch
    end
    st = host.esxcli.storage
    rule = st.nmp.satp.rule
    claim = st.core.claiming
    tag = host.esxcli.vsan.storage.tag
    disks.each do |disk|
      puts "Claiming #{disk.disk.displayName} as #{opts[:claim_type]} ..."
      dev = disk.disk.canonicalName
      rules = rule.list(:satp => "VMW_SATP_LOCAL").select do |r|
        r.Device == dev && ["disable_ssd", "enable_ssd", 'enable_capacity_flash'].member?(r.Options)
      end.map{|x| x.Options}
      # For tagging capacity_flash, we should use new command under vsan namespace
      if opts[:claim_type] == 'capacity_flash'
        tag.add(
          :disk => dev,
          :tag => "capacityFlash"
        )
        next
      elsif opts[:claim_type] == 'hdd'
        remove_rules = ['enable_ssd', 'enable_capacity_flash']
        add_rules = ['disable_ssd']
      elsif opts[:claim_type] == 'ssd'
        remove_rules = ['disable_ssd', 'enable_capacity_flash']
        add_rules = ['enable_ssd']
      else
        err "Claim type #{opts[:claim_type]} is not supported"
      end
      remove_rules.each do |remove_rule|
        if rules.member?(remove_rule)
          puts "  Found existing rule #{remove_rule}, clearing ..."
          rule.remove(
            :device => dev,
            :option => remove_rule,
            :satp => "VMW_SATP_LOCAL"
          )
        end
      end
      add_rules.each do |add_rule|
        if !rules.member?(add_rule)
          puts "  No existing rule #{add_rule}, adding ..."
          rule.add(
            :device => dev,
            :option => add_rule,
            :satp => "VMW_SATP_LOCAL"
          )
        end
      end

      puts "  Refreshing state"
      claim.reclaim(:device => dev)
    end
  end
end


opts :host_wipe_non_vsan_disk do
  summary "Wipe disks with partitions other than VSAN partitions"
  arg :hosts, nil, :lookup => [VIM::HostSystem], :multi => true
  opt :disk, "Disk to be wiped clean (multiple allowed)", :type => :string, :multi => true
  opt :force, "Do it for real", :type => :boolean
  opt :interactive, "Select disks to wipe from given disk list, cannot be set together with parameter 'disks'", :type => :boolean
end

# Accpet user input index of disks,
# help to decide which disks user want to remove.
# disks: Array of HostScsiDisk
def _disk_selection_question2 valid_indices
  regex = /^[1-9][0-9]*$/
  inputs = []
  begin
    puts "Please input index of disks to be wiped, use comma to separate, input 'none' to skip:"
    input = $stdin.gets.chomp
    input.strip!
    if input.casecmp('abort') == 0
      inputs = []
      return inputs
    end
    inputs = input.split(',').map{|x| x.strip}.uniq
    inputs = inputs.select{|x| x =~ regex}
    inputs = inputs.map{|x| x.to_i}
    if !inputs.empty?
      # Verify user input indexes
      # all input indexes must exist in entity array
      invalid_inputs = inputs.select{|x| !valid_indices.member?(x)}
      if invalid_inputs.length > 0
        puts "Detected invalid index of disks: #{invalid_inputs}, please try again:"
        inputs = []
      end
    end
  end while inputs.empty?
  inputs = inputs.sort
  inputs
end

def host_wipe_non_vsan_disk hosts, opts
  opts[:disk] ||= []
  if !opts[:interactive] && opts[:disk].length == 0
    err "Need to specify either --interface or --disk"
  end
  if opts[:interactive] && opts[:disk].length > 0
    err "Need to specify only one of --interface and --disk"
  end
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

    if opts[:interactive]
      nonVsanDisks = host_info['disks'].select do |disk|
        disk.state != 'inUse'
      end
      if nonVsanDisks.length == 0
        puts "No non-VSAN disks, skipping"
        next
      end
      t = Terminal::Table.new()
      t << ['Index', 'Disk info', 'Partition info']
      t.add_separator

      nonVsanDisks.each_with_index do |disk, idx|
        makemodel = [
          disk.disk.vendor,
          disk.disk.model
        ].compact.map{|x| x.strip}.join(" ")
        capacity = disk.disk.capacity
        size = capacity.block * capacity.blockSize
        partitions = disk['partition'].map do |x|
          partSize = x.Size.to_f / 1024**3
          type = x['typeStr']
          str = "  #{x.Partition}: %.2f GB, type = #{type}" % partSize
          if type == "vmfs"
            vmfsStr = x['vmfsDs'].map do |vmfsDs|
              "'#{dsListProps[vmfsDs]['name']}'"
            end.join(", ")
            if vmfsStr
              str += " (#{vmfsStr})"
            end
          end
          str
        end
        row = [
           idx + 1,
           [
             "Disk: #{disk.disk.displayName}",
             "Make/Model: #{makemodel}",
             "Type: #{disk.disk.ssd ? "SSD" : "HDD"}",
             "Size: #{size / 1024**3} GB",
           ].join("\n"),
           ([
             "Partition table:",
           ] + partitions).join("\n"),
        ]
        t << row
        if idx != nonVsanDisks.length - 1
          t.add_separator
        end
      end
      puts t
      choices = _disk_selection_question2((1..nonVsanDisks.length).to_a)
      opts[:disk] = choices.map{|x| nonVsanDisks[x - 1].disk.canonicalName}
    end

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
      puts "  Host: #{host_name}"
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
          puts "erase all data on disk #{disk.disk.canonicalName} for real."
        end
      end
      puts ""
    end
  end

end

opts :proactive_rebalance do
  summary "Configure proactive rebalance for Virtual SAN"
  arg :cluster, "Path to ClusterComputeResource", :lookup => [VIM::ClusterComputeResource], :multi => false
  opt :start, "Start proactive rebalance", :type => :boolean
  opt :time_span, "Determine how long this proactive rebalance lasts in seconds, only be valid when option 'start' is specified", :type => :int
  opt :variance_threshold, "Configure the threshold, that only if disk's used_capacity/disk_capacity exceeds this threshold(comparing to the disk with the least fullness in the cluster), disk is qualified for proactive rebalance, only be valid when option 'start' is specified", :type => :float
  opt :time_threshold, "Threashold in seconds, that only when variance threshold continuously exceeds this threshold, corresponding disk will be involved to proactive rebalance, only be valid when option 'start' is specified", :type => :int
  opt :rate_threshold, "Determine how many data in MB could be moved per hour for each node, only be valid when option 'start' is specified", :type => :int
  opt :stop, "Stop proactive rebalance", :type => :boolean
end

def proactive_rebalance cluster, opts = {}
  if !opts[:start] && !opts[:stop]
    puts "Please specify proactive rebalance operation: start or stop"
    return
  end
  _proactive_rebalance cluster, opts
end

opts :proactive_rebalance_info do
  summary "Retrieve proactive rebalance status for Virtual SAN"
  arg :cluster, "Path to ClusterComputeResource", :lookup => [VIM::ClusterComputeResource], :multi => false
end

def proactive_rebalance_info cluster
  _proactive_rebalance cluster
end

def _proactive_rebalance cluster, opts = {}
  conn = cluster._connection
  pc = conn.propertyCollector
  _run_with_rev(conn, "dev") do
    model = VsanModel.new(
      [cluster],
      [],
      :allow_multiple_clusters => false
    )
    hosts = model.basic['vsan_enabled_hosts']
    hosts_props = model.basic['hosts_props']

    if hosts.empty?
      puts "No host specified to rebalance, stop proceeding"
      return
    end

    results = {}
    errors = {}
    lock = Mutex.new
    hosts.map do |host|
      Thread.new do
        host_name = hosts_props[host]['name']
        begin
          lock.synchronize do
            if opts[:start] || opts[:stop]
              puts "#{Time.now}: Processing Virtual SAN proactive rebalance on host #{host_name} ..."
            else
              puts "#{Time.now}: Retrieving proactive rebalance information from host #{host_name} ..."
            end
          end
          c1 = conn.spawn_additional_connection
          host_id = host._ref.partition('-').last
          async_sys = VIM::VimHostVsanAsyncSystem(c1, "ha-vsan-async-system-#{host_id}")

          # Lower version host doesn't has clom tool
          if hosts_props[host]['config.product'].version < '6.0.0'
            errors[host_name] = "Operation not supported on host lower than 6.0.0"
          elsif !hosts_props[host]['configManager.vsanSystem'].config.enabled
            errors[host_name] = "Virtual SAN is disabled"
          elsif opts[:start]
            async_sys.StartProactiveRebalance(
              :timeSpan => opts[:time_span],
              :varianceThreshold => opts[:variance_threshold],
              :timeThreshold => opts[:time_threshold],
              :rateThreshold => opts[:rate_threshold]
            )
          elsif opts[:stop]
            async_sys.StopProactiveRebalance()
          else
            # Default behavior is to query rebalance info
            results[host_name] = async_sys.GetProactiveRebalanceInfo()
          end
        rescue VIM::VsanFault => fault
          msg = ''
          if fault.faultMessage
            fault.faultMessage.each do |x|
              msg += "#{x.message}"
              if x != fault.faultMessage.last
                x += "\n"
              end
            end
          else
            msg = fault.message
          end
          errors[host_name] = "#{msg}"
        rescue Exception => ex
          errors[host_name] = "#{ex.class}: #{ex.message}"
        end
      end
    end.each{|t| t.join}

    if opts[:start] || opts[:stop]
      puts ""
      msg = "Proactive rebalance has been started!"
      msg = "Proactive rebalance has been stopped!" if opts[:stop]
      err_msg = "Failed to start proactive rebalance on following hosts:"
      err_msg = "Failed to stop proactive rebalance on following hosts:" if opts[:stop]
      if errors.empty?
        puts msg
      else
        puts err_msg
        t = Terminal::Table.new()
        t << ['Host',        'Error']
        t.add_separator

        errors.map{|h, e| t << [h, e]}

        puts t
      end
      puts ""
      return
    end

    # Common output
    disks = model.get_physical_vsan_disks
    vsan_disks_info = {}
    vsan_disks_info.merge!(
      _vsan_host_disks_info(Hash[hosts.map{|h| [h, hosts_props[h]['name']]}])
    )
    # Filter out SSD and unhealthy disks
    disks = disks.select{|k, v| v['isSsd'] != 1 && v['rvc_health_str'] == "OK"}

    disks.each do |k, v|
      v['esxcli'] = vsan_disks_info[v['uuid']]
      if v['esxcli']
        v['host'] = v['esxcli']._get_property :host
      end
    end

    # Filter out any disks from witness node
    disks = disks.select {|k, v| !v['esxcli'].nil?}
    puts ""

    variance_threshold = 0.3
    time_threshold = 0
    rate_threshold = 51200

    runnings = results.select{|k, v| v.running}
    not_runnings = results.select{|k, v| !v.running}
    if !runnings.empty?
      inconsistent = false
      first_node = runnings.values.first
      start_time = first_node.startTs
      stop_time = first_node.stopTs
      variance_threshold = first_node.varianceThreshold
      time_threshold = first_node.timeThreshold
      rate_threshold = first_node.rateThreshold

      runnings.each do |k, v|
        start_time = v.startTs if (v.startTs < start_time)
        stop_time = v.stopTs if (v.stopTs > stop_time)

        if variance_threshold != v.varianceThreshold ||
          time_threshold != v.timeThreshold ||
          rate_threshold != v.rateThreshold
          inconsistent = true
          break
        end
      end

      if inconsistent
        RVC::Util::err "The proactive rebalance paramaters are\n" \
                       "different between hosts. Please restart\n" \
                       "the proactive rebalance operation!"
        return
      end

      puts "Proactive rebalance start: #{start_time}"
      puts "Proactive rebalance stop: #{stop_time}"
      if !not_runnings.empty?
        puts "Proactive rebalance is not running on the following hosts:"
        not_runnings.each{|k, v| puts k}
      end

      if !errors.empty?
        puts "Failed to retrieve proactive rebalance info from following hosts:"
        errors.each{|k, v| puts "#{k}: #{v}"}
      end
    else
      puts "Proactive rebalance is not running!"
    end
    puts "Max usage difference triggering rebalancing: %.2f%%" % (variance_threshold * 100)

    mean_fullness = 0.0
    min_fullness = 1.0
    max_variance = 0.0
    disks.each do |k, v|
      mean_fullness += v['fullness']
      min_fullness = v['fullness'] if (v['fullness'] < min_fullness)
    end
    if !disks.empty?
      mean_fullness = (mean_fullness.to_f / disks.size).round(2)
      avg_variance = mean_fullness - min_fullness
    end

    disks.each do |k, v|
      v['variance'] = v['fullness'] - min_fullness
      max_variance = v['variance'] if (v['variance'] > max_variance)
      v['fullness_above_threshold'] = (v['variance'] - variance_threshold).round(2)
      if v['fullness_above_threshold'] > 0
        rate = [(v['fullness'] - mean_fullness), v['fullness_above_threshold']].min
        rate = (rate < 0) ? 0 : rate
        v['bytes_to_move'] = v['capacity'] * rate
      end
    end
    max_fullness = max_variance + min_fullness

    puts "Average disk usage: %.2f%%" % (mean_fullness * 100)
    puts "Maximum disk usage: %.2f%% (%.2f%% above minimum disk usage)" % [max_fullness * 100, max_variance * 100]
    puts "Imbalance index: %.2f%%" % (avg_variance * 100)
    disks = disks.select{|k, v| v['bytes_to_move'] && v['bytes_to_move'] > 0}
    if !disks.empty?
      puts "Disks to be rebalanced:"
      disks = disks.values.sort_by do |x|
        host_props = hosts_props[x['host']]
        host_props ? host_props['name'] : ''
      end
      groups = disks.group_by{|x| x['esxcli'] ? x['esxcli'].VSANDiskGroupUUID : nil}

      t = Terminal::Table.new()
      t << ['DisplayName', 'Host', 'Disk usage above threshold', 'Data to move']
      t.add_separator
      groups.each do |group, disks|
        disks.each do |x|
          info = x['esxcli']
          host_props = hosts_props[x['host']]
          t << [
            info ? info.DisplayName : 'N/A',
            host_props ? host_props['name'] : '',
            "%.2f%%" % (x['fullness_above_threshold'] * 100),
            "%.4f GB" % [x['bytes_to_move'] / 1024**3]]
        end
        if group != groups.keys.last
          t.add_separator
        end
      end

      puts t
    else
      puts "No disk detected to be rebalanced"
    end
    puts ""
  end
end

$EXPLAIN_INACCESSIBLE_VSWP = <<-EOS

VM vswp file is used for memory swapping for running VMs by ESX. In VMware
virtual SAN a vswp file is stored as a separate virtual SAN object. When a vswp
object goes inaccessible, memory swapping will not be possible and the VM may
crash when next time ESX tries to swap the memory for the VM. Deleting the
inaccessible vswp object will not make thing worse, but it will eliminate the
possibility for the object to regain accessibility in future time if this is
just a temporary issue (e.g. due to network failure or planned maintenance).

Due to a known issue in vSphere 5.5, it is possible for Virtual SAN to have
done incomplete deletions of vswp objects. In such cases, the majority of
components of such objects were deleted while a minority of components were
left unavailable (e.g. due to one host being temporarily down at the time of
deletion). It is then possible for the minority to resurface and present
itself as an inaccessible object because a minority can never gain quorum.
Such objects waste space and cause issues for any operations involving data
evacuations from hosts or disks. This command employs heuristics to detect
this kind of left-over vswp objects in order to delete them.

It will not cause data loss by deleting the vswp object. The vswp object will
be regenerated when the VM is powered on next time.

EOS

opts :purge_inaccessible_vswp_objects do
  summary "Search and delete inaccessible vswp objects on a virtual SAN cluster." \
          "\n#{$EXPLAIN_INACCESSIBLE_VSWP}"
  arg :cluster_or_host, nil, :lookup => [VIM::ClusterComputeResource, VIM::HostSystem]
  opt :force, "Force to delete the inaccessible vswp objects quietly "    \
              "(no interactive confirmations)", :type => :boolean
end

def purge_inaccessible_vswp_objects cluster_or_host, opts
  conn = cluster_or_host._connection
  pc = conn.propertyCollector

  _run_with_rev(conn, "dev") do
    model = VsanModel.new([cluster_or_host])
    connected_hosts = model.basic['connected_hosts']
    hosts_props = model.basic['hosts_props']
    host = connected_hosts.first
    # Error out when network partition detected
    partitions = model.get_partitions()
    if partitions.length > 1
      puts "#{Time.now}: WARNING: VSAN Cluster network partition detected. " \
           "Please resolve the network issue and run this command again."
      return
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
    disks = vsanIntSys.query_physical_vsan_disks(:props => ['uuid', 'owner'])
    hostDiskMap = Hash[disks.map do |uuid, props|
      [uuid, hostUuidMap[props['owner']]]
    end]

    puts "#{Time.now}: Collecting all inaccessible Virtual SAN objects..."
    # Check for inaccessible VSAN objects first
    cmmds_ret = vsanIntSys.query_cmmds([{:type => 'CONFIG_STATUS'}])
    bad = []
    cmmds_ret.each do |x|
      state = _assessAvailabilityByStatus(x['content']['state'])
      if !state['DATA_AVAILABLE'] || !state['QUORUM']
        bad << x['uuid']
      end
    end
    puts "#{Time.now}: Found #{bad.length} inaccessbile objects."
    if bad.empty?
      return
    end

    puts "#{Time.now}: Selecting vswp objects from inaccessible objects by checking their extended attributes..."
    cmmds_ret = vsanIntSys.query_cmmds(
      bad.map{ |uuid| {:type => 'DOM_OBJECT', :uuid => uuid}})
    host_bads = Hash[connected_hosts.map{|host| [host, []] }]
    only_witness = {}
    # Find the host for each remaining active component because we can only
    # query extended attributes with bypassDom mode from its hosting node
    cmmds_ret.each do |x|
      comps = _components_in_dom_config(x['content']).select do |comp|
        ['Component', 'Witness'].member?(comp['type']) && \
        comp['attributes']['componentState'] == 5 #ACTIVE
      end
      if comps.empty?
        next
      end
      first_comp = comps.select{|c| c['type'] == 'Component'}.first
      if first_comp
        comp_host = hostDiskMap[first_comp['diskUuid']]
        if !comp_host
          next
        end
        host_bads[comp_host] << x['uuid']
      else
        # only witness components left
        only_witness[x['uuid']] = comps.map{|c| c['componentUuid']}
      end
    end
    host_bads.select!{|h, uuids| !uuids.empty?}
    # Query objects' extended attributes from the host
    bad_vswp = {}
    bad_query = {}
    host_bads.each do |h, uuids|
      begin
        hostIntSys = hosts_props[h]['configManager.vsanInternalSystem']
        objAttrs = hostIntSys.query_vsan_obj_extattrs(:uuids => uuids)
        uuids.each do |uuid|
          attr = objAttrs[uuid]
          if attr['Error']
            bad_query[uuid] = attr['Error']
          elsif attr['Object class'] == 'vmswap'
            bad_vswp[uuid] = attr
          end
        end
      rescue Exception => ex
        reason = "#{ex.class}: #{ex.message}"
        puts "Ignoring extended attributes query error on host #{h.name}: #{reason}"
        uuids.each{|uuid| bad_query[uuid] = reason}
      end
      if !bad_query.empty?
        puts "Following inaccessabile objects will be skipped for further " \
             "processing due to errors in querying extended attributes:"
        t = Terminal::Table.new()
        t << ['Object UUID', 'Error']
        t.add_separator()
        bad_query.each{|uuid, reason| t << [uuid, reason]}
        puts t
      end
    end
    puts "#{Time.now}: Found #{bad_vswp.length} inaccessible vswp objects."

    if !bad_vswp.empty?
      t = Terminal::Table.new()
      t << ['Object UUID', 'Object Path', 'Size']
      t.add_separator()
      bad_vswp.each do |uuid, attr|
        size = attr['Object size']
        size_s = "%dB (%.2f GB)" % [size, size.to_f / 1024**3]
        t << [uuid, attr['Object path'], size_s]
      end
      puts t
      puts "#{Time.now}: Ready to delete the inaccessible vswp object...\n"
      puts $EXPLAIN_INACCESSIBLE_VSWP
      obj_deleted = 0
      delete_all = opts[:force]
      bad_vswp.each do |uuid, attr|
        if !delete_all
          # Ask user to choose whether to delete each object
          choice = ''
          while true
            puts "Delete #{attr['Object path']} (#{uuid})?"
            print "  [Y] Yes  [N] No  [A] yes to All  [C] Cancel to all: "
            choice = $stdin.gets.chomp.downcase
            if ['y','n','a','c'].member?(choice)
              break
            end
            puts "Error: the choice cannot be recognized! Please retry."
          end

          if choice == 'n'
            next
          elsif choice == 'a'
            delete_all = true
          elsif choice == 'c'
            puts "Cancel deleting virtual SAN objects."
            break
          end
        else
          puts "Deleting #{attr['Object path']} (#{uuid})..."
        end
        begin
          result = vsanIntSys.DeleteVsanObjects(
            :uuids => [uuid],
            :force => true
          )
          if result.first.success
            puts "Deleted."
            obj_deleted += 1
          end
        rescue Exception => ex
          puts "Ignoring object deletion error for #{uuid}: #{ex.class}: #{ex.message}"
        end
      end
      puts "#{Time.now}: Deleted #{obj_deleted} inaccessible vswp objects."
    end

    if !only_witness.empty?
      puts <<-EOS

#{Time.now}: Found #{only_witness.length} inaccessible objects left with only witness
but no active data components. In this case extended attributes cannot be
retrieved to determine whether these are vswp objects, so this command will
query all VMs on virtual SAN datastore to see if they are used as namespace or
virtual disk by any VMs.
EOS
      ds_list = host.datastore
      ds_props = pc.collectMultiple(ds_list, 'summary.type')
      ds = ds_props.select{|k, x| x['summary.type'] == "vsan"}.keys.first
      vms = ds.vm
      vmsProps = pc.collectMultiple(vms,
        'name', 'config.hardware.device', 'summary.config', 'layoutEx.file'
      )
      objToPathMap = {}
      vms.each do |vm|
        begin
          _get_vm_obj_uuids(vm, vmsProps).each do |uuid, path|
            if only_witness[uuid]
              vmProps = vmsProps[vm]
              vm_name = vmProps['name']
              is_namespace = vmProps['namespaceUuid'] == uuid
              objToPathMap[uuid] ||= []
              objToPathMap[uuid] << "#{vm_name}: #{is_namespace ? 'Namespace directory' : path }"
            end
          end
        rescue Exception => ex
          puts "Ignoring VM query error for #{vm}: #{ex.class}: #{ex.message}"
        end
      end

      t = Terminal::Table.new()
      t << ['Object UUID', 'Witness UUID', 'In Use by VM:Path']
      t.add_separator()
      # Display in-use objects first
      only_witness.each do |uuid, witness|
        if objToPathMap[uuid]
          t << [uuid, witness.join("\n"), objToPathMap[uuid].join("\n")]
        end
      end
      # Then display objects not in-use, which is likely vswp objects
      only_witness.select! {|uuid, w| objToPathMap[uuid] == nil }
      only_witness.each do |uuid, witness|
        t << [uuid, witness.join("\n"), '']
      end
      puts t
      if only_witness.empty?
         puts "None of the above objects looks like vswp objects. Skip deleting them."
      else
         puts <<-EOS
Found #{only_witness.length} objects in above table that are not used as namespace or virtual disk
by any VMs. These are possibly vswp objects. Please make sure all hosts are
connected and not running maintenance mode, and make sure all disks are
correctly plugged in and seen by virtual SAN. This way, if some data components
of an inaccessible object come back active, rerun this command and it will be
able to determine whether the object is vswp object. Otherwise, it may possibly
cause a tentative inactive data component to be deleted by forcibly deleting the
inaccessible objects. If all data components of an inaccessible object are
permanently deleted or missing, it is okay to delete the object because it will
not cause data loss by deleting the leftover witnesses.

EOS
        if opts[:force]
          puts "Above objects cannot be deleted with \"force\" option. If you "  \
               "are sure that you want to delete them, please run this command " \
               "without \"force\" option and delete them one by one."
        else
          obj_deleted = 0
          only_witness.each do |uuid, witness|
            # Ask user to choose whether to delete each object
            choice = ''
            while true
              puts "Are you sure that you want to delete object #{uuid}?"
              print "  [Y] Yes  [N] No  [C] Cancel to all: "
              choice = $stdin.gets.chomp.downcase
              if ['y','n','c'].member?(choice)
                break
              end
              puts "Error: the choice cannot be recognized! Please retry."
            end
            if choice == 'n'
              next
            elsif choice == 'c'
              puts "Cancel deleting virtual SAN objects."
              break
            end
            begin
              result = vsanIntSys.DeleteVsanObjects(
                :uuids => [uuid],
                :force => true
              )
              if result.first.success
                puts "Deleted."
                obj_deleted += 1
              end
            rescue Exception => ex
              puts "Ignoring object deletion error for #{uuid}: #{ex.class}: #{ex.message}"
            end
          end
          puts "#{Time.now}: Deleted #{obj_deleted} inaccessible objects whose " \
               "active components are only witnesses."
        end
      end
    end
  end

end

