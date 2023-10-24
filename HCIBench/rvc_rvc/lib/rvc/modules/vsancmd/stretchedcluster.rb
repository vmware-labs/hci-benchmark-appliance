require 'pp'
require 'rbvmomi'
require 'rvc/vim'

# Copy the helper method from health.rb.
# There is a progress() to monitor task progress but we cannot use that
# for some reason when sub-task is spawned from this task.
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

opts :witness_info do
  summary "Show witness host information for a vSAN Stretched Cluster"
  arg :cluster, "A cluster with virtual SAN stretched cluster enabled",
      :lookup => [VIM::ClusterComputeResource], :multi => false
end

def witness_info cluster
  witness_info = get_witness_hosts(cluster)
  if !witness_info.nil?
    puts "Found witness host for vSAN stretched cluster."
    _print_witness_info cluster.name, witness_info
  else
    puts "Cannot find witness host for the cluster. This is not a " \
         "vSAN stretched cluster."
  end
end

def _print_witness_info cluster_name, witness_info
  t = Terminal::Table.new()
  t << ['Stretched Cluster', cluster_name]
  witness_info.each do |witness|
     wh = witness[:host]
     t.add_separator
     witnessMode = ""
     if witness[:metadataMode]
        witnessMode = " (metadata witness)"
     end
     t << ['Witness Host Name', (wh ? wh.name: '') + witnessMode]
     t << ['Witness Host UUID', witness[:nodeUuid]]
     t << ['Preferred Fault Domain', witness[:preferredFdName]]
     t << ['Unicast Agent Address', witness[:unicastAgentAddr]]
  end
  puts t
end

opts :config_witness do
  summary "Configure witness host to form a vSAN Stretched Cluster"
  arg :cluster, "A cluster with virtual SAN enabled",
      :lookup => [VIM::ClusterComputeResource], :multi => false
  arg :witness_host, "Witness host for the stretched cluster",
      :lookup => [VIM::HostSystem], :multi => false
  arg :preferred_fault_domain, "preferred fault domain for witness host",
      :type => :string
  opt :metadata, "Config the host as metadata node or not",
      :type => :boolean
end

def config_witness cluster, witness_host, preferred_fault_domain, opts
  puts "Configuring witness host for the cluster..."
  scMo = get_stretched_cluster_mo(cluster)
  begin
    task = scMo.VSANVcAddWitnessHost(
      :cluster => cluster,
      :witnessHost => witness_host,
      :preferredFd => preferred_fault_domain,
      :diskMapping => nil,
      :metadataMode=> opts[:metadata] ? true: false
    )
    watch_task cluster._connection, task._ref
  rescue RbVmomi::Fault => e
    pp e.fault.faultMessage
  end
end

opts :remove_witness do
  summary "Remove witness host from a vSAN Stretched Cluster"
  arg :cluster, "A cluster with virtual SAN stretched cluster enabled",
      :lookup => [VIM::ClusterComputeResource], :multi => false
  opt :host, "A witness host", :lookup => [VIM::HostSystem],
      :multi => false
end

def remove_witness cluster, opts
  if opts[:host]
    puts "Removing witness host from the cluster..."
    remove_witness_host(cluster, opts[:host], opts[:host][:name])
    return
  end

  witness_info = get_witness_hosts(cluster)
  if witness_info.nil?
    RVC::Util::err "Error: No witness host was found configured for " \
                   "the cluster. Are you sure this is a stretched " \
                   "cluster?"
  end
  puts "Found witness host for vSAN stretched cluster."
  _print_witness_info cluster.name, witness_info
  puts "Removing witness host from the cluster..."

  witness_info.each do |witness|
     wh = witness[:host]
     if !wh.nil?
        wh_ip = wh[:name]
     end
     remove_witness_host(cluster, wh, wh_ip)
  end
end
