# Copyright (c) 2011 VMware, Inc.  All Rights Reserved.
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

require 'rvc/vim'
require "terminal-table"

opts :create do
  summary "Create a cluster"
  arg :dest, nil, :lookup_parent => VIM::Folder
end

def create dest
  folder, name = *dest
  folder.CreateClusterEx(:name => name, :spec => {})
end


opts :add_host do
  summary "Add a host to a cluster"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource
  arg :hostnames, nil, :multi => true
  opt :username, "Username", :short => 'u', :default => 'root'
  opt :password, "Password", :short => 'p', :default => ''
  opt :insecure, "Ignore SSL thumbprint", :short => 'k'
  opt :force, "Force, e.g when host is already managed by other VC"
end

def add_host cluster, hostnames, opts
  sslThumbprint = nil
  hostnames.each do |hostname|
    while true
      spec = {
        :force => opts[:force],
        :hostName => hostname,
        :userName => opts[:username],
        :password => opts[:password],
        :sslThumbprint => sslThumbprint,
      }
      task = cluster.AddHost_Task :spec => spec,
                                  :asConnected => true
      begin
        one_progress task
        break
      rescue VIM::SSLVerifyFault
        unless opts[:insecure]
          puts "SSL thumbprint: #{$!.fault.thumbprint}"
          $stdout.write "Accept this thumbprint? (y/n) "
          $stdout.flush
          answer = $stdin.readline.chomp
          err "Aborted" unless answer == 'y' or answer == 'yes'
        end
        sslThumbprint = $!.fault.thumbprint
      end
    end
  end
end


opts :remove_host do
  summary "Remove host(s) from inventory"
  arg :host, nil, :lookup => VIM::HostSystem, :multi => true
end

def remove_host hosts
  conn = hosts.first._connection
  pc = conn.propertyCollector

  begin
    hostsProps = pc.collectMultiple(hosts,
    'name',
    'runtime.inMaintenanceMode',
    'configManager.vsanSystem'
  )
  rescue Exception
    if conn.vsan_standalone_mode
      puts 'Host is unreachable, remove it directly.'
      tasks = []
      hosts.each do |host|
        tasks << host.Destroy_Task()
      end
      progress(tasks)
      return
    else
      raise 'Host is unreachable, please remove it with VCenter UI.'
    end
  end

  vsanSystems = hostsProps.map{|h,p| p['configManager.vsanSystem']}
  vsanEnabled = pc.collectMultiple(vsanSystems, 'config.enabled')

  tasks = []
  hosts.each do |host|
    hostname = hostsProps[host]['name']
    inMaintenanceMode = hostsProps[host]['runtime.inMaintenanceMode']
    vsanSystem = hostsProps[host]['configManager.vsanSystem']
    hostVsanEnabled = vsanEnabled[vsanSystem]['config.enabled']

    puts "Removing host #{hostname}"

    if (!conn.vsan_standalone_mode && hostVsanEnabled)
      err "vSAN enabled host should be moved out the cluster before removing it" \
          "from inventory to properly disable vSAN on it"
    end
    if !inMaintenanceMode
      err "Abort! host #{hostname} is not in maintenance mode"
    end

    tasks << host.Destroy_Task()
  end

  progress(tasks)
end


opts :delete do
  summary "Delete a cluster"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource
end

def delete cluster
  if cluster.host.length != 0
    err "Abort! There are still Hosts in cluster, remove them before delete cluster"
  end
  task = cluster.Destroy_Task()
  one_progress(task)
end


opts :configure_ha do
  summary "Configure HA on a cluster"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource, :multi => true
  opt :disabled, "Disable HA", :default => false
end

def configure_ha clusters, opts
  spec = VIM::ClusterConfigSpecEx(
    :dasConfig => {
      :enabled => !opts[:disabled],
    }
  )
  tasks = clusters.map do |cluster|
    cluster.ReconfigureComputeResource_Task(:spec => spec, :modify => true)
  end
  progress(tasks)
  childtasks = tasks.map{|t| t.child_tasks}.flatten.compact
  if childtasks && childtasks.length > 0
    progress(childtasks)
  end

end

opts :configure_drs do
  summary "Configure DRS on a cluster"
  opt :disabled, "Disable DRS", :default => false
  opt :mode, "DRS mode (manual, partiallyAutomated, fullyAutomated)", :type => :string
  arg :cluster, "Path to a Cluster", :lookup => VIM::ClusterComputeResource, :multi => true
end

def configure_drs clusters, opts
  clusterSpec = VIM::ClusterConfigSpecEx(
    :drsConfig => {
      :defaultVmBehavior => opts[:mode] ? opts[:mode].to_sym : nil,
      :enabled => !opts[:disabled]
    }
  )
  tasks = clusters.map do |cluster|
    cluster.ReconfigureComputeResource_Task(:modify => true, :spec => clusterSpec)
  end
  progress(tasks)
end

opts :configure_swap do
  summary "Configure VM Swap Placement on a cluster"
  opt :mode, "Swap mode (hostLocal, vmDirectory)", :type => :string
  arg :cluster, "Path to a Cluster", :lookup => VIM::ClusterComputeResource, :multi => true
end

def configure_swap clusters, opts
  clusterSpec = VIM::ClusterConfigSpecEx(
    :vmSwapPlacement => opts[:mode]
  )
  tasks = clusters.map do |cluster|
    cluster.ReconfigureComputeResource_Task(:modify => true, :spec => clusterSpec)
  end
  progress(tasks)
end

opts :recommendations do
  summary "List recommendations"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource
end

def recommendations cluster
  # Collect everything we need from VC with as few calls as possible
  pc = cluster._connection.serviceContent.propertyCollector
  recommendation, hosts, datastores = cluster.collect 'recommendation', 'host', 'datastore'
  if recommendation.length == 0
    puts "None"
    return
  end
  targets = recommendation.map { |x| x.target }
  recommendation.each { |x| targets += x.action.map { |y| y.target } }
  targets += hosts
  targets += datastores
  targets.compact!
  name_map = pc.collectMultiple(targets, 'name')

  # Compose the output (tries to avoid making any API calls)
  t = Terminal::Table.new()
  t << ['Key', 'Reason', 'Target', 'Actions']
  recommendation.each do |r|
    target_name = r.target ? name_map[r.target]['name'] : ""
    actions = r.action.map do |a|
      action = "#{a.class.wsdl_name}: #{name_map[a.target]['name']}"
      dst = nil
      if a.is_a?(RbVmomi::VIM::ClusterMigrationAction)
        dst = a.drsMigration.destination
      end
      if a.is_a?(RbVmomi::VIM::StorageMigrationAction)
        dst = a.destination
      end
      if dst
        if !name_map[dst]
          name_map[dst] = {'name' => dst.name}
        end
        action += " (to #{name_map[dst]['name']})"
      end
      action
    end
    t << [r.key, r.reasonText, target_name, actions.join("\n")]
  end
  puts t
end

def _filtered_cluster_recommendations cluster, key, type
  recommendation = cluster.recommendation
  if key && key.length > 0
    recommendation.select! { |x| key.member?(x.key) }
  end
  if type && type.length > 0
    recommendation.select! { |x| (type & x.action.map { |y| y.class.wsdl_name }).length > 0 }
  end
  recommendation
end

opts :apply_recommendations do
  summary "Apply recommendations"
  arg :cluster, nil, :lookup => VIM::ClusterComputeResource
  opt :key, "Key of a recommendation to execute", :type => :string, :multi => true
  opt :type, "Type of actions to perform", :type => :string, :multi => true
end

def apply_recommendations cluster, opts
  pc = cluster._connection.serviceContent.propertyCollector
  recommendation = _filtered_cluster_recommendations(
    cluster, opts[:key], opts[:type]
  )
  all_tasks = []

  # We do recommendations in chunks, because VC can't process more than a
  # few migrations anyway and this way we get more fair queuing, less
  # timeouts of long queued migrations and a better RVC user experience
  # due to less queued tasks at a time. It would otherwise be easy to
  # exceed the screensize with queued tasks
  while recommendation.length > 0
    recommendation.pop(20).each do |r|
      begin
        targets = r.action.map { |y| y.target }
        recent_tasks = pc.collectMultiple(targets, 'recentTask')
        prev_tasks = targets.map { |x| recent_tasks[x]['recentTask'] }
        cluster.ApplyRecommendation(:key => r.key)
        recent_tasks = pc.collectMultiple(targets, 'recentTask')
        tasks = targets.map { |x| recent_tasks[x]['recentTask'] }
        all_tasks += (tasks.flatten - prev_tasks.flatten)
      rescue VIM::InvalidArgument
      end
    end

    if all_tasks.length > 0
      progress all_tasks
      all_tasks = []
    end

    recommendation = _filtered_cluster_recommendations(
      cluster, opts[:key], opts[:type]
    )
  end
end

