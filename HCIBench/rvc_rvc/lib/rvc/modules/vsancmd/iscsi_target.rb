require 'rbvmomi'
require 'rvc/vim'

# Implement vsan.iscsi_target.* rvc commands

# load vSAN iSCSI target (VIT) Vmomi types
load File.join(File.dirname(__FILE__), 'iscsi_target.api.txt')

# NOTE: This command is only a placeholder with the rest part TBD.
# command vsan.iscsi_target.query_version
opts :query_version do
  summary "Query vSAN iSCSI target version on ESX host"
  arg :host, "ESX host IP address", :lookup => [VIM], :multi => false
end

def query_version host
   conn = host._connection
   vhv = VIM::VimHostVsanIscsiTargetSystem(conn, 'vit')
   ver = vhv.QueryVsanIscsiTargetSystemVersion()
   puts "vSAN iSCSI target version: #{ver}"
end
