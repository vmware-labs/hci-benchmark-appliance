require 'fileutils'
require 'rvc/vim'
require 'rbvmomi/pbm'

class Spinner
  def initialize
    @i = 0
    @spinners = '-\|/-\|/'
  end

  def spin
    if $stdout.tty?
      @i += 1
      @i = 0 if @i >= @spinners.length
      $stdout.write "\b#{@spinners[@i..@i]}"
      $stdout.flush
    end
  end

  def done
    if $stdout.tty?
      puts "\b- done"
    end
  end

  def abort
    if $stdout.tty?
      puts "\b"
    end
  end

  def begin text
    if $stdout.tty?
      $stdout.write "#{Time.now}: #{text} -"
      $stdout.flush
    else
      puts "#{Time.now}: #{text}"
    end
  end
end

RbVmomi::VIM::VirtualMachine
class RbVmomi::VIM::VirtualMachine
  def downloadAsOvf destinationDir, h = {}
    note, = self.collect 'summary.config.annotation'
    note = YAML.load(note) || {}
    if note.is_a?(Hash) && note['lease']
      note.delete('lease')
      ReconfigVM_Task(spec: {annotation: YAML.dump(note)}).wait_for_completion
    end

    spinner = h[:spinner]
    vmName = self.name
    destinationDir = File.join(destinationDir, vmName)
    FileUtils.mkdir_p destinationDir
    lease = self.ExportVm
    while !['done', 'error', 'ready'].member?(lease.state)
      sleep 1
    end
    if lease.state == "error"
      raise lease.error
    end
    leaseInfo = lease.info

    progress = 5
    keepAliveThread = Thread.new do
      while progress < 100
        lease.HttpNfcLeaseProgress(:percent => progress)
        lastKeepAlive = Time.now
        while progress < 100 && (Time.now - lastKeepAlive).to_i < (leaseInfo.leaseTimeout / 2)
          sleep 1
        end
      end
    end

    pp leaseInfo.deviceUrl
    ovfFiles = leaseInfo.deviceUrl.map do |x|
      next if !x.disk
      url = x.url
      if url =~ /(https?:\/\/)\*\//
        url = url.gsub(/(https?:\/\/)(\*)\//, "\\1#{_connection.host}/")
      end
      uri = URI.parse(url)
      http = Net::HTTP.new(uri.host, uri.port)
      http.read_timeout = 30 * 60
      if uri.scheme == 'https'
        http.use_ssl = true
        http.verify_mode = OpenSSL::SSL::VERIFY_NONE
      end
      headers = {'cookie' => _connection.cookie}
      localFilename = File.join(destinationDir, x.targetId)
      spinner.begin "Downloading disk to #{localFilename}" if spinner
      s = 0
      File.open(localFilename, 'w') do |fileIO|
        http.get(uri.path, headers) do |bodySegment|
          fileIO.write bodySegment
          s += bodySegment.length;
          #$stdout.write "."
          #$stdout.flush
          spinner.spin if spinner
        end
      end

      spinner.done if spinner
      progress += 90 / leaseInfo.deviceUrl.length

      {:size => s, :deviceId => x.key, :path => x.targetId}
    end.compact
    puts if spinner

    progress = 100
    keepAliveThread.join
    lease.HttpNfcLeaseComplete()

    ovfMgr = self._connection.serviceContent.ovfManager
    descriptor = ovfMgr.CreateDescriptor(
      :obj => self,
      :cdp => {
        :ovfFiles => ovfFiles,
        :includeImageFiles => false,
        :exportOption => ['extraConfig']
      }
    )
    File.open(File.join(destinationDir, "#{vmName}.ovf"), 'w') do |io|
      io.write descriptor.ovfDescriptor
    end
  end
end

opts :download do
  summary "Download VM in OVF format"
  arg :destination, nil, :type => :string
  arg :vms, nil, :lookup => VIM::VirtualMachine, :multi => true
  opt :exp_opt, "Export options", :type => :string, :multi => true, :required => false
end

def download destination, vms, opts
  spinner = Spinner.new
  vms.each do |vm|
    vm.downloadAsOvf destination, :spinner => spinner, :exportOption => opts[:exp_opt]
  end
end

opts :ovf_deploy do
  summary "Deploy OVF template"
  arg :vm_name, "Path to new VM", :lookup_parent => VIM::Folder
  arg :url, "URL to OVF descriptor file", :type => :string
  opt :cluster, "Destination cluster. Instead of host+rp", :lookup => VIM::ComputeResource
  opt :host, "Destination host", :lookup => VIM::HostSystem, :required => false, :type => :string
  opt :datastore, "Destination datastore", :lookup => VIM::Datastore, :required => true, :type => :string
  opt :network, "Destination network (used for all vNics)", :lookup => VIM::Network, :required => true, :type => :string
  opt :rp, "(Optional) Destination resource pool. Default: Host's root resource pool", :lookup => VIM::ResourcePool, :type => :string
  opt :property, "(Optional) Property in format key=value", :type => :string, :multi => true
  opt :vservice, "(optional) Name of vservice to bind to", :type => :string, :multi => true
  opt :select_dhcp_policy, "(Optional) Use DHCP IP allocation policy"
  opt :profile, "VM Storage Profile", :lookup => RbVmomi::PBM::PbmCapabilityProfile
end

rvc_alias :ovf_deploy

def ovf_deploy dst, url, opts
  folder, name = *dst

  if !opts[:cluster] && !opts[:host]
    err "Need to supply either cluster or host"
  end
  if opts[:cluster]
    if !opts[:host]
      conn = opts[:cluster]._connection
      pc = conn.propertyCollector
      hosts = opts[:cluster].host
      hosts_props = pc.collectMultiple(hosts, 'runtime.connectionState')
      connected_hosts = hosts_props.select do |k,v|
        v['runtime.connectionState'] == 'connected'
      end.keys
      hosts = connected_hosts

      if hosts.length == 0
        err "Couldn't find any connected hosts"
      end
      opts[:host] = hosts.first
    end
    if !opts[:rp]
      opts[:rp] = opts[:cluster].resourcePool
    end
  end

  ovf_uri = URI.parse url
  ovf_str = open(ovf_uri, 'r').read
  ovf_xml = Nokogiri::XML(ovf_str).remove_namespaces!
  ovf_networks = Hash[ovf_xml.xpath('//NetworkSection/Network').map do |x|
    desc = x.xpath('Description').first
    [x['name'], desc ? desc : '']
  end]

  ovf_props = Hash[ovf_xml.xpath('//VirtualSystem/ProductSection/Property').map do |x|
    label = x.xpath('Label').first
    [
      x['key'],
      {
        :label => label ? label.content : '',
        :type => x['type']
      }
    ]
  end]
  ovf_props.each do |k,v|
    puts "Available property '#{k}' (label = #{v[:label]}, type = #{v[:type]})"
  end

  network_mappings = Hash[ovf_networks.keys.map{|x| [x, opts[:network]]}]
  puts "networks: #{network_mappings.map{|k, v| k + ' = ' + v.name}.join(', ')}"

  property_mappings = Hash[opts[:property].map do |x|
    k,v = x.split("=", 2)
    if ovf_props[k][:type] == "boolean"
      v = (["true", "True", "1"].member?(v)) ? "True" : "False"
    end
    [k, v]
  end]
  if !opts[:rp]
    opts[:rp] = opts[:host].parent.resourcePool
  end
  vmProfile = nil
  if opts[:profile]
    vmProfile = [VIM::VirtualMachineDefinedProfileSpec(
      :profileId => opts[:profile].profileId.uniqueId
    )]
  end
  conn = opts[:host]._connection
  vm = conn.serviceContent.ovfManager.deployOVF(
    :uri => ovf_uri,
    :vmName => name,
    :vmFolder => folder,
    :host => opts[:host],
    :resourcePool => opts[:rp],
    :datastore => opts[:datastore],
    :networkMappings => network_mappings,
    :propertyMappings => property_mappings,
    :vservice => opts[:vservice],
    :defaultProfile => vmProfile
  )
  if opts[:select_dhcp_policy]
    task = vm.ReconfigVM_Task(:spec => {
      :vAppConfig => {
        :ipAssignment => {:ipAllocationPolicy => "dhcpPolicy"}
      }
    })
    progress([task])
  end
  vm
end

