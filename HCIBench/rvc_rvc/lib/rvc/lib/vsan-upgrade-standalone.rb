require 'pp'
require 'rbvmomi'
require 'json'
require 'rvc/util'
require 'rvc/lib/vsangeneric'
require 'rvc/lib/vsanupgrade'
require 'trollop'
require 'rbvmomi/trollop'

cmdopts = Trollop.options do
  banner <<-EOS
vSAN Upgrade Tool standalone version. Do not invoke directly.

Usage:
       vsan-upgrade-standlone [options] clusterMoId

where [options] are:
EOS

  opt :action, "Action", :type => :string, :required => true
  opt :exclude_host, "Specified hosts which won't be involved during file system upgrade; with this option set, object upgrade will be skipped", :type => :string, :multi => true
  opt :ignore_objects, "Ignore objects upgrade", :type => :boolean
  opt :downgrade_format, "Downgrade disk format and file system, be available only if there is no v2 object in vSAN cluster", :type => :boolean
  opt :allow_reduced_redundancy, "Removes the need for one disk group worth of free space, by allowing reduced redundancy during disk upgrade", :type => :boolean
  opt :statusfile, "Path to where to store status information", :type => :string
end

clusterMoId = ARGV[0]
action = cmdopts[:action]
if !['preflight-check', 'upgrade'].member?(action)
  puts "Invalid action"
  exit(-1)
end

class RbVmomi::VIM
  def self.connectEx opts
    fail unless opts.is_a? Hash
    fail "host option required" unless opts[:host]
    opts[:cookie] ||= nil
    opts[:user] ||= 'root'
    opts[:password] ||= ''
    opts[:ssl] = true unless opts.member? :ssl or opts[:"no-ssl"]
    opts[:insecure] ||= false
    opts[:port] ||= (opts[:ssl] ? 443 : 80)
    opts[:path] ||= '/sdk'
    opts[:ns] ||= 'urn:vim25'
    rev_given = opts[:rev] != nil
    opts[:rev] = '4.0' unless rev_given
    opts[:debug] = (!ENV['RBVMOMI_DEBUG'].empty? rescue false) unless opts.member? :debug

    new(opts).tap do |vim|
      unless opts[:cookie]
        sessMgr = vim.serviceContent.sessionManager
        if opts[:clone_ticket]
          sessMgr.CloneSession(:cloneTicket => opts[:clone_ticket])
        else
          sessMgr.Login :userName => opts[:user], :password => opts[:password]
        end
      end
      unless rev_given
        rev = vim.serviceContent.about.apiVersion
        vim.rev = [rev, '5.5'].min
      end
    end
  end
end

logger = nil
if OS.windows?
  logger = FileLogger.new("#{ENV['TEMP']}\\vpxd-vsanupgrade.log")
else
  logger = FileLogger.new("/tmp/vpxd-vsanupgrade.log")
end
logger.info "CLONETICKET = #{ENV['CLONETICKET']}"
rev = '5.5'
if ENV['UNSTABLEVER']
  rev = ENV['UNSTABLEVER']
end
logger.info "UNSTABLEVER = #{ENV['UNSTABLEVER']}"
conn = RbVmomi::VIM.connectEx(
  :host => 'localhost',
  :clone_ticket => ENV['CLONETICKET'],
  :insecure => true,
  :rev => rev,
)
begin
  cluster = RbVmomi::VIM::ClusterComputeResource(conn, clusterMoId)
  logger.info "vSAN cluster: #{cluster.name}"
  opts = { # XXX
    :exclude_host => (cmdopts[:exclude_host] || []).map{|moId| RbVmomi::VIM::HostSystem(conn, moId)},
    :ignore_objects => cmdopts[:ignore_objects],
    :downgrade_format => cmdopts[:downgrade_format],
    :resume_backup => false,
    :allow_reduced_redundancy => cmdopts[:allow_reduced_redundancy]
  }
  hosts = cluster.host

  if action == 'preflight-check'
    upgradetask = RealUpgradeTask.new(conn, nil, rev)
    res = _v2_ondisk_upgrade_PerformUpgradePreflightCheck(hosts, opts)
    out = upgradetask.serialize(res, true)
    puts out
  elsif action == 'upgrade'
    upgradetask = RealUpgradeTask.new(conn, cmdopts[:statusfile], rev)

    pid, size = `ps ax -o pid,rss | grep -E "^[[:space:]]*#{$$}"`.strip.split.map(&:to_i)
    logger.info "Memory size: #{size} KB"

    _v2_ondisk_upgrade_backend(
      upgradetask, conn, hosts,
      opts.merge({
        :logger => logger,
      })
    )

    pid, size = `ps ax -o pid,rss | grep -E "^[[:space:]]*#{$$}"`.strip.split.map(&:to_i)
    logger.info "Memory size: #{size} KB"
    logger.close

    res = upgradetask.currentStatus
    if res
      puts res
    end
  end
ensure
  conn.close
end
