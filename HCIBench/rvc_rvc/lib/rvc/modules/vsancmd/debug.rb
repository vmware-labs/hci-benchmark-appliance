require 'rbvmomi'
require 'rvc/vim'


# Get a connection to vSAN management service
def getVsanMgmtConnection(conn)
   if conn.serviceContent.about.apiType == "VirtualCenter"
      path = "/vsanHealth"
   else
      path = "/vsan"
   end
   vsanConn = VIM.new(
            :host => conn.host,
            :port => 443,
            :insecure => true,
            :ns => "urn:vsan",
            :ssl => true,
            :rev => "6.7",
            :path => path
         )
   vsanConn.cookie = conn.cookie
   vsanConn.debug = conn.debug
   return vsanConn
end


opts :mob do
   summary "Start/Stop vSAN managed object browser"
   arg :conn, "vCenter/ESX connection", :lookup => [VIM], :multi => false
   opt :start, "Start vSAN MOB", :type => :boolean
   opt :stop, "Stop vSAN MOB", :type => :boolean
end

def mob conn, opts
   if opts[:start] && opts[:stop]
      err "option --start is not allowed with --stop"
   end
   if !opts[:start] && !opts[:stop]
      err "one of the options is required: --start, --stop"
   end
   debugSystem = VIM::VsanDebugSystem(getVsanMgmtConnection(conn), 'vsanDebugSystem')
   if opts[:start]
      debugSystem.VsanStartMobService()
      hostName = conn.host
      if hostName == "127.0.0.1" || hostName == "localhost" || hostName == "localhost.localdomain"
         hostName = Socket.gethostname
      end
      puts "vSAN managed object browser is started, please access: https://#{hostName}/vsan/mob."
   else
      debugSystem.VsanStopMobService()
      puts "vSAN managed object browser is stopped."
   end
end
