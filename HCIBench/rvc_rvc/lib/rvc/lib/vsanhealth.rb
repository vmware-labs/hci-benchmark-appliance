require 'rbvmomi'
require 'rvc/vim'
require 'terminal-table'
require 'open-uri'
require 'resolv'

load File.join(File.dirname(__FILE__), 'vsanmgmt_disk_mgmt.api.txt')
patchedMgmtApiFile = File.join(File.dirname(__FILE__), 'vsanmgmt.api.rb')
if File.exists?(patchedMgmtApiFile)
  # In vCenter context
  load patchedMgmtApiFile
else
  # In local env
  load File.join(File.dirname(__FILE__), 'vsanmgmt.api.txt')
end

RbVmomi::VIM::HostSystem
class RbVmomi::VIM::HostSystem

  def _vsanHealthSystem
    conn = self._connection
    if self._ref == "ha-host"
      return VIM::VimHostVsanHealthSystem(conn, 'ha-vsan-health-system')
    else
      id = self._ref.split('-').last
      return VIM::VimHostVsanHealthSystem(conn, "ha-vsan-health-system-#{id}")
    end
  end

  def vsanHealthSystem
    @vsanHealthSystem ||= _vsanHealthSystem
  end

  def _vsanClusterHealthSystem
    conn = self._connection
    if self._ref == "ha-host"
      return VIM::VimClusterVsanClusterHealthSystem(conn, 'ha-vsan-cluster-health-system')
    else
      id = self._ref.split('-').last
      return VIM::VimClusterVsanClusterHealthSystem(conn, "ha-vsan-cluster-health-system-#{id}")
    end
  end

  def vsanClusterHealthSystem
    @vsanClusterHealthSystem ||= _vsanClusterHealthSystem
  end

  def runVmdkLoadTest opts = {}
    return vsanHealthSystem.QueryVsanHostRunVmdkLoadTest(opts)
  end

  def prepareVmdkLoadTest opts = {}
    return vsanHealthSystem.QueryVsanHostPrepareVmdkLoadTest(opts)
  end

  def queryObjectHealth opts = {}
    return vsanHealthSystem.VsanHostQueryObjectHealthSummary(opts)
  end

  def capturePcap opts = {}
    return vsanHealthSystem.VsanHostQueryVsanPcap(opts)
  end

  def runIperfClient opts = {}
    return vsanHealthSystem.VsanHostQueryRunIperfClient(opts)
  end

  def runIperfServer opts = {}
    return vsanHealthSystem.VsanHostQueryRunIperfServer(opts)
  end

  def _vsanPerformanceManager
    conn = self._connection
    moId = nil
    if self._ref == "ha-host"
      moId = 'ha-vsan-performance-manager'
    else
      id = self._ref.split('-').last
      moId = 'ha-vsan-performance-manager-%s' % [id]
    end
    return VIM::VsanPerformanceManager(conn, moId)
  end

  def vsanPerformanceManager
    @vsanPerformanceManager ||= _vsanPerformanceManager
  end
end

class ::RbVmomi::VIM

  # In Standalone VSAN Mgmt Mode, there is Non-VC but Vsan Mgmt service act
  # as VC, all of the available commands will work as normal VC mode and
  # some inapplicable commands will be disabled.
  # However, it's transparent to VSAN users(through RVC)
  def vsan_standalone_mode
    serviceContent.about.apiType == 'VsanMgmt'
  end

  def getVsanServiceVersion(conn, ns)
    serviceXmlUri = "/sdk/vsanServiceVersions.xml"
    serviceName = ns.split(":")[1]
    hostname = conn.host
    if Resolv::IPv6::Regex =~ hostname
      hostname = 'https://' + '[' + conn.host + ']'
    else
      hostname = 'https://' + conn.host
    end
    versionXml = open(
      hostname + serviceXmlUri,
      { ssl_verify_mode: conn.http.verify_mode }
    )
    versionXmlDoc = Nokogiri::XML(versionXml)
    return versionXmlDoc.xpath('//name')[0].text == ns ?
      versionXmlDoc.xpath('//version')[0].text : nil
  rescue
    return nil
  end

  def vsanHealth
    conn = self
    port = @opts[:port] || 443
    ns = 'urn:vsan'
    vsanversion = getVsanServiceVersion(conn, ns)
    if vsanversion.nil?
       # 6.0 is an unrecognized version and server
       # will hadle it by using default vsan version
       vsanversion = '6.0'
    end
    hsConn = VIM.new(
      :host => conn.host,
      :port => self.vsan_standalone_mode ? port : 443,
      :insecure => true,
      :ns => ns,
      :ssl => true,
      :rev => vsanversion,
      :path => '/vsanHealth'
    )
    hsConn.cookie = conn.cookie
    hsConn.debug = conn.debug
    return hsConn
  end

  def vsanVcObjectSystem
    vos = VIM::VsanObjectSystem(
      self.vsanHealth,
      'vsan-cluster-object-system'
    )
    return vos
  end

  def vsanVcPerformanceManager
    vpm = VIM::VsanPerformanceManager(
      self.vsanHealth,
      'vsan-performance-manager'
    )
    return vpm
  end
end

def mapHealthCode health
  healthMap = {
    'green' => "Passed",
    'yellow' => "Warning",
    'red' => 'Error',
    'unknown' => "Unknown",
    'info' => "Info"
  }
  if healthMap[health]
    return healthMap[health]
  end
  return health
end

def replaceHealthIcon(values, indexes)
  indexes.each do |index|
    case values[index]
    when "green"
      values[index] = "OK"
    when "yellow", "red"
      values[index] = "Issue Found"
    end
  end
end

def watch_task conn, taskId
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

def get_feature_name feature
  feature.downcase!
  validFeatures = { "health" => "Health", "sizing" => "Sizing" }
  if not validFeatures.has_key?(feature)
     puts "feature option can only be one of #{validFeatures.keys}"
     return [nil, nil]
  else
     return [feature, validFeatures[feature]]
  end
end

#To fix the PR 1758623. Currently the MOR entry pattern can be one of below:
#dynamic type:
##	mor:ManagedObjectReference:<mo._wsdl_name>:<mo._moId>
##	mor:ManagedObjectReference:HostSystem:<host._moId>
##	HostReference:host_name
##	Host_name
##mor type:
##	ManagedObjectReference:HostSystem:<host._moId>
##listMor type(entry of listMor, caller need to break listMor set to entry before call the function ):
##	mor:ManagedObjectReference:HostSystem:<host._moId>
##	HostReference:<host_name>, HostReference:<host_name>
##	ManagedObjectReference:VirtualMachine:<vm._moId>
##	mor:ManagedObjectReference:<mo._wsdl_name>:<mo._moId>

def get_mor_name(x, conn, opts)
  parts = x.split(":")
  offset = 0
  if parts[0] == "mor"
    offset = 1
  end
  if parts[0+offset] == "ManagedObjectReference"
    if !opts[:morTable][parts[2+offset]]
      mor = VIM::const_get(parts[1+offset]).new(conn, parts[2+offset])
      opts[:morTable][parts[2+offset]] = mor.name
    end
    x = opts[:morTable][parts[2+offset]]
  else
    x = parts.last
  end
  return x
end

##
#Install health or sizing offline bundle on hosts in the clusters.
#@param clusters:  the clusters, in whose hosts the feature offline bundle will be installed.
#@param feature:   for now can be either 'health' or 'sizing'.
#@param opts:      dict include options.:dry_run(only validate) and :force(not prompt confirmation)
def install_feature_on_clusters clusters, feature, opts = {}
  featureKey, featureDisplayName = get_feature_name(feature)
  if featureKey.nil?
    return
  end
  conn = clusters.first._connection
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')
  clusters.each do |cluster|
    preCheckRet = nil
    begin
      preCheckRet =
        vvchs.VsanClusterHealthExtensionManagmentPreCheck(:cluster => cluster,
                                                          :install => true,
                                                          :feature => featureKey)
      if preCheckRet.overallResult == true && opts[:dry_run]
        puts "#{cluster.name} is OK for installing vSAN #{featureDisplayName} Extension on ESXs."
      end
      if preCheckRet.overallResult == false
        puts "#{cluster.name} is NOT OK for installing vSAN #{featureDisplayName} Extension on ESXs."
        preCheckRet.results.each do |result|
          result.testDetails.each do |detail|
            displayGenericHealthDetails(detail, :indent => 0,
                                        :replaceHealthIconInTable => true,
                                        :printTabelLabel => true,
                                        :conn => conn)
          end
        end
      end
      if preCheckRet.vumRegistered == true
        puts "Warning: VUM has been registered to current vCenter Server,"
        puts "         please aware the consequences if proceed to install."
      end
    rescue Exception => ex
      puts "Failed to check cluster #{cluster.name}: #{ex.message}"
      if ex.is_a?(VIM::LocalizedMethodFault) || ex.is_a?(RbVmomi::Fault)
        ex = ex.fault
      end
      if ex.is_a?(VIM::VimFault)
        ex.faultMessage.each do |msg|
          puts "   #{msg.key}: #{msg.message}"
        end
      end
    end
    if !opts[:dry_run] && preCheckRet.overallResult == true
      begin
        if preCheckRet.vumRegistered == true
          bInstall = _questionnaire(
                                  "Do you want to proceed to install? Yes/No",
                                  ["yes", "no"],
                                  "yes"
                                    )
          if !bInstall
            err "Aborted"
          end
        end
        puts "This command is going to install the vSAN #{featureDisplayName} Extension VIB"
        puts "on all hosts in the cluster. To complete the install all hosts"
        puts "are going to be rebooted. It is required for DRS to be in fully"
        puts "automated mode such that a rolling reboot can be performed. A"
        puts "rolling reboot puts one host at a time in Maintenance Mode and"
        puts "then reboots it, then proceeding with the next until all hosts"
        puts "are rebooted. By doing so all VMs keep running and the reboot"
        puts "doesn't impact production workloads. Due to this rolling reboot"
        puts "the install task will take a while (minutes to hours), depending"
        puts "on how many host are in the cluster and how many VMs are running."
        puts ""

        if opts[:force]
          proceed = true
        else
          proceed = _questionnaire(
            "Enabling vSAN #{featureDisplayName} will rolling reboot host, do you want to proceed? [Yes/No]",
            ["yes", "no"],
            "yes"
          )
        end
        if !proceed
          err "Aborted"
        end

        t = vvchs.VsanHealthPrepareCluster(:cluster => cluster, :feature => featureKey)
        t = VIM::Task(conn, t._ref)
        watch_task(conn, t._ref)
        res = {}
        res[t] = t.info.error || t.info.result
        if res[t].is_a?(VIM::LocalizedMethodFault)
          puts ""
          raise res[t]
        end
      rescue Exception => ex
        puts "Failed to prepare cluster #{cluster.name}: #{ex.message}"
        if ex.is_a?(VIM::LocalizedMethodFault) || ex.is_a?(RbVmomi::Fault)
          ex = ex.fault
        end
        if ex.is_a?(VIM::VimFault)
          ex.faultMessage.each do |msg|
            puts "   #{msg.key}: #{msg.message}"
          end
        end
      end
    end
  end
end

##
#Uninstall health or sizing offline bundle on hosts in the clusters.
#@param clusters:  the clusters, in whose hosts the feature offline bundle will be installed.
#@param feature:   for now can be either 'health' or 'sizing'.
#@param opts:      dict include options.:dry_run(only validate) and :force(not prompt confirmation)
def uninstall_feature_on_clusters clusters, feature, opts = {}
  featureKey, featureDisplayName = get_feature_name(feature)
  if featureKey.nil?
    return
  end
  conn = clusters.first._connection
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')
  clusters.each do |cluster|
    begin
      preCheckRet =
        vvchs.VsanClusterHealthExtensionManagmentPreCheck(:cluster => cluster,
                                                          :install => false,
                                                          :feature => featureKey)
      if preCheckRet.overallResult == true && opts[:dry_run]
        puts "#{cluster.name} is OK to uninstall vSAN #{featureDisplayName} Extension on ESXs."
      end
      if preCheckRet.overallResult == false
        puts "#{cluster.name} is NOT OK to uninstall vSAN #{featureDisplayName} Extension on ESXs."
        preCheckRet.results.each do |result|
          result.testDetails.each do |detail|
            displayGenericHealthDetails(detail, :indent => 0,
                                        :replaceHealthIconInTable => true,
                                        :printTabelLabel => true,
                                        :conn => conn)
          end
        end
      end
    rescue Exception => ex
      puts "Failed to check cluster #{cluster.name}: #{ex.message}"
      if ex.is_a?(VIM::LocalizedMethodFault) || ex.is_a?(RbVmomi::Fault)
        ex = ex.fault
      end
      if ex.is_a?(VIM::VimFault)
        ex.faultMessage.each do |msg|
          puts "   #{msg.key}: #{msg.message}"
        end
      end
    end
    if !opts[:dry_run] && preCheckRet.overallResult == true
      begin
        puts "This command is going to uninstall the vSAN #{featureDisplayName} Extension VIB"
        puts "from all hosts in the cluster. To complete the uninstall all hosts"
        puts "are going to be rebooted. It is required for DRS to be in fully"
        puts "automated mode such that a rolling reboot can be performed. A"
        puts "rolling reboot puts one host at a time in Maintenance Mode and"
        puts "then reboots it, then proceeding with the next until all hosts"
        puts "are rebooted. By doing so all VMs keep running and the reboot"
        puts "doesn't impact production workloads. Due to this rolling reboot"
        puts "the uninstall task will take a while (minutes to hours), depending"
        puts "on how many host are in the cluster and how many VMs are running."
        puts ""

        t = vvchs.VsanHealthUninstallCluster(:cluster => cluster, :feature => featureKey)
        t = VIM::Task(conn, t._ref)
        watch_task(conn, t._ref)
        res = {}
        res[t] = t.info.error || t.info.result
        if res[t].is_a?(VIM::LocalizedMethodFault)
          puts ""
          raise res[t]
        end
      rescue Exception => ex
        puts "Failed on cluster #{cluster.name}: #{ex.message}"
        if ex.is_a?(VIM::LocalizedMethodFault) || ex.is_a?(RbVmomi::Fault)
          ex = ex.fault
        end
        if ex.is_a?(VIM::VimFault)
          ex.faultMessage.each do |msg|
            puts "   #{msg.key}: #{msg.message}"
          end
        end
      end
    end
  end
end

def parse_listmor_type(x, conn, opts)
  xList = []
  y = x.split(",")
  y.each do |yy|
    if conn && yy.length > 0
      yy = yy.lstrip
      xList << get_mor_name(yy, conn, opts)
    end
  end
  if xList.size > 0
    x = xList.join(", ")
  end
  return x
end

def displayGenericHealthDetails(details, opts = {})
  conn = opts[:conn]
  indent = (opts[:indent].times.map{" "}.join) || ""
  if details.is_a?(VIM::VsanClusterHealthResultTable)
    numCol = details.columns.length
    if opts[:replaceHealthIconInTable]
      hi = details.columns.index{|c| c.type == "health"}
    end
    t = Terminal::Table.new()
    t << details.columns.map{|x| x.label}
    t.add_separator
    details.rows.each do |row|
      if row.values.length > numCol
        RVC::Util.err "Row has more columns than defined by table"
      end
      # XXX: Adjust based on type
      values = []
      row.values.dup.each_with_index do |x, i|
        if details.columns[i].type == "health"
          x = mapHealthCode(x)
        end
        opts[:morTable] ||= {}
        if details.columns[i].type == "listMor"
          x = parse_listmor_type(x, conn, opts)
        end
        if (details.columns[i].type == "mor" or details.columns[i].type == "dynamic") && conn
          if x.include?"listMor:"
             x = x.split('listMor:')[-1]
             x = parse_listmor_type(x, conn, opts)
          elsif x.length > 0
            x = get_mor_name(x, conn, opts)
          end
        end
        values << x
      end
      if opts[:replaceHealthIconInTable] && hi && values.length > hi
        replaceHealthIcon(values, [hi])
      end
      t << values
      row.nestedRows.each do |nestedRow|
        if nestedRow.values.length > numCol
          RVC::Util.err "Nested row has more columns than defined by table"
        end
        items = nestedRow.values.dup
        if opts[:replaceHealthIconInTable] && hi && items.length > hi
          replaceHealthIcon(items, [hi])
        end
        items[0] = "  %s" % items[0]
        t << items
      end
    end
    if opts[:printTableLabel] && details.label != ""
      puts details.label
    end
    puts t.to_s.split("\n").map{|x| "#{indent}#{x}" }.join("\n")
  elsif details.is_a?(VIM::VimClusterVsanClusterHealthResultValues)
    t = Terminal::Table.new()
    t << ["Values"]
    t.add_separator
    details.values.each do |val|
      t << [val]
    end
    puts t.to_s.split("\n").map{|x| "#{indent}#{x}" }.join("\n")
  else
    pp details
  end
end

def cluster_feature_status clusters, feature, opts = {}
  featureKey, featureDisplayName = get_feature_name(feature)
  if featureKey.nil?
    return
  end
  conn = clusters.first._connection
  pc = conn.propertyCollector
  vvchs = VIM::VimClusterVsanVcClusterHealthSystem(conn.vsanHealth, 'vsan-cluster-health-system')
  clusters.each do |cluster|
    begin
      res = vvchs.VsanHealthGetClusterStatus(:cluster => cluster, :feature => featureKey)
      res = JSON.load(res)
      if res['status'] == 'red'
        state = "incomplete, see issues"
      elsif res['status'] == 'yellow'
        state = "in progress"
      elsif res['status'] == 'unknown'
        state = "unknown"
      else
        state = "OK"
      end
      goal = "installed"
      if res['goalState'] == 'uninstalled'
        goal = 'not installed'
      end
      puts "Configuration of ESX vSAN #{featureDisplayName} Extension: #{goal} (#{state})"
      hosts = (res['untracked'] + res['tracked'].keys).map do |host|
        VIM::HostSystem(conn, host)
      end
      # Fix PR 1685156 We shouldn't report any issue if the status is OK/Green
      if state != "OK"
         hostsProps = pc.collectMultiple(hosts, 'name')
         if res['issues'].length > 0
           puts "Issues:"
           res['issues'].each do |issue|
             puts "  #{issue}"
           end
         end
      end
      if res['untracked'].length > 0
        res['untracked'].each do |host|
          host = VIM::HostSystem(conn, host)
          hostname = hostsProps[host]['name']
          puts "Host is not (yet) tracked: #{hostname}"
        end
      end
      if ['unknown', 'red'].member?(res['status'])
        puts "Per-Host details:"
        res['tracked'].each do |host, info|
          host = VIM::HostSystem(conn, host)
          hostname = hostsProps[host]['name']
          puts "  Host '#{hostname}':"
          puts "    Status: #{info['status']}"
          if info['issues'].length > 0
            puts "    Issues:"
            info['issues'].each do |issue|
              puts "      #{issue}"
            end
          end
        end
      end

      if res['status'] == "green"
        hosts = cluster.host
        hosts.each do |h|
          vib = h.esxcli.software.vib.list.find{|x| x.Name == "vsan#{featureKey}"}
          if !vib
            puts "WARNING: Host '#{h.name}' doesn't have VIB installed"
          end
        end
      end
      if featureKey == 'health'
         verify_health_versions(cluster, vvchs)
      end
    rescue Exception => ex
      puts "Failed to get status of cluster #{cluster.name}: #{ex.message}"
      if ex.is_a?(VIM::LocalizedMethodFault) || ex.is_a?(RbVmomi::Fault)
        ex = ex.fault
      end
      if ex.is_a?(VIM::VimFault)
        ex.faultMessage.each do |msg|
          puts "   #{msg.key}: #{msg.message}"
        end
      end
    end
  end
end

def verify_health_versions cluster, vvchs
   versions = vvchs.VsanVcClusterQueryVerifyHealthSystemVersions(:cluster => cluster)
   versions.hostResults.each do |result|
     if !result.version.nil?
       if result.version == "0.0"
         puts "Host '#{result.hostname}' doesn't have health system installed"
       else
         puts "Host '#{result.hostname}' has health system version '#{result.version}' installed"
       end
     else
       pp result.error
       puts "ERROR: Host '#{result.hostname}' '#{PP.pp(result.error, '')}'"
     end
   end
   puts "vCenter Server has health system version '#{versions.vcVersion}' installed"
end

