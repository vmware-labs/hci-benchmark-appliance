require 'rbvmomi'

$VSAN_STRETCHEDCLUSTER_SUPPORTED = true

class ::RbVmomi::VIM
  def vsanStretch
    conn = self
    hsConn = VIM.new(
      :host => conn.host, :port => 443, :insecure => true,
      :ns => 'urn:vsan',
      :ssl => true,
      :rev => "6.9.0",
      :path => '/vsanHealth'
    )
    hsConn.cookie = conn.cookie
    hsConn.debug = conn.debug
    return hsConn
  end
end

# This function has been deprecated as it can only return
# first witness/metadata node.
# Retrieve the witness host for a cluster. If the cluster is a stretched
# cluster and has been configured properly, it will return the witness
# host information, otherwise return null if it is not stretched cluster.
def get_witness_host(cluster, ignoreError=true)
  witness_info = get_witness_hosts(cluster)
  if witness_info.nil? || witness_info.empty?
    return nil
  end
  return witness_info[0]
end

# Retrieve the witness host for a cluster. If the cluster is a stretched
# cluster and has been configured properly, it will return the witness
# host information, otherwise return null if it is not stretched cluster.
def get_witness_hosts(cluster, ignoreError=true)
  begin
    conn = cluster._connection
    vscs = get_stretched_cluster_mo(cluster)
    witnessHosts = vscs.VSANVcGetWitnessHosts(:cluster => cluster)
    if witnessHosts.nil? || witnessHosts.empty?
      return nil
    end

    witnessHosts.each do |item|
       item[:host] = VIM::HostSystem(conn, item[:host]._ref)
    end

    return witnessHosts
  rescue
    if !ignoreError
      raise
    end
    return nil
  end
end

def remove_witness_host cluster, host, host_ip
  scMo = get_stretched_cluster_mo(cluster)
  task = scMo.VSANVcRemoveWitnessHost(
    :cluster => cluster,
    :witnessHost => host,
    :witnessAddress => host_ip
  )
  watch_task cluster._connection, task._ref
end

def get_stretched_cluster_mo cluster
  conn = cluster._connection
  return VIM::VimClusterVsanVcStretchedClusterSystem(conn.vsanStretch,
    'vsan-stretched-cluster-system')
end

# Retrieve the stretched cluster host managed object for the host
def get_stretched_cluster_host_mo host
  sid = host._ref.split('-').last
  VIM::VimHostVsanStretchedClusterSystem(conn.vsanStretch,
      "ha-vsan-stretched-cluster-system-#{sid}")
end
