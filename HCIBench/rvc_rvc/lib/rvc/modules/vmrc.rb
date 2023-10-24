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

require 'tmpdir'
require 'digest/sha2'
require 'zip'
require 'rbconfig'


ARCH = RbConfig::CONFIG['arch']
ON_WINDOWS = !(RbConfig::CONFIG['host_os'] =~ /(mswin|mingw)/).nil?
ON_MAC     = !(RbConfig::CONFIG['host_os'] =~ /(darwin)/).nil?
ON_LINUX   = !(RbConfig::CONFIG['host_os'] =~ /(linux)/).nil?

def vmrc_url arch
  # TODO - we should put this on Internet, such as github, but I don't have permission
  # to upload these files to the original place.
  base = "http://sc-prd-rdops-templates.eng.vmware.com/nimbus-templates/nimbus-resources/tools/vmrc/"
  if ON_WINDOWS
    return base + "VMware-VMRC-9.0.0.msi"
  elsif ON_LINUX
    return base + "VMware-Remote-Console-9.0.0.x86_64.bundle"
  elsif ON_MAC
    return base + "VMware-Remote-Console-9.0.0.dmg"
  end
  fail "Unsupported platform for VMRC."
end

def vmrc_installed?
  if ON_WINDOWS
    output = `wmic product where "Name like 'VMware Remote Console'" get Name`
    return !(output =~ /VMware Remote Console/).nil?
  elsif ON_LINUX
    output = `type vmrc 2>&1`
    return !(output =~ /vmrc is hashed/).nil?
  elsif ON_MAC
    output = `osascript -e 'id of app "VMware Remote Console"' 2>&1`
    return output.strip! == 'com.vmware.vmrc'
  end
  fail "Unsupported platform for VMRC."
end

opts :view do
  summary "Spawn a VMRC"
  text "The VMware Remote Console allows you to interact with a VM's virtual mouse, keyboard, and screen."
  opt :install, "Automatically install VMRC", :short => 'i'
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
end

rvc_alias :view
rvc_alias :view, :vmrc
rvc_alias :view, :v

def view vms, opts
  unless vmrc_installed?
    if opts[:install]
      install
    end
    err "VMRC not found. You may need to run vmrc.install."
  end

  vms.each do |vm|
    moref = vm._ref
    ticket = vm._connection.serviceInstance.content.sessionManager.AcquireCloneTicket
    host = vm._connection._host
    spawn_vmrc moref, host, ticket
  end
end

def spawn_vmrc moref, host, ticket
  uri = "vmrc://clone:#{ticket}@#{host}/?moid=#{moref}"
  if ON_WINDOWS
    `start #{uri}`
  elsif ON_LINUX
    `vmrc #{uri}`
  elsif ON_MAC
    `open #{uri}`
  end
end


opts :install do
  summary "Install VMRC"
end

def install
  if vmrc_installed?
    puts "VMRC has been installed."
    return
  end

  puts "Please download installer at #{vmrc_url ARCH} and run manually."
end

opts :remote_console_url do
  summary "Get remote console URL"
  arg :vm, nil, :lookup => VIM::VirtualMachine, :multi => true
  opt :no_html5, "Don't use HTML5 client", :type => :boolean
end

def remote_console_url vms, opts = {}
  conn = single_connection vms
  pc = conn.serviceContent.propertyCollector
  about = conn.serviceContent.about
  settingMgr = conn.serviceContent.setting
  sessionMgr = conn.serviceContent.sessionManager

  vcUuid = about.instanceUuid
  ver = about.version

  htmlPort = 9443
  if opts[:port]
    htmlPort = opts[:port]
  end
  server_guid = conn.serviceInstance.content.about.instanceUuid
  setting = settingMgr.setting.find{|x| x.key == "VirtualCenter.FQDN"}
  if !setting
    err "Expected to find 'VirtualCenter.FQDN' setting for VC"
  end
  vcenter_fqdn = setting.value
  if vcenter_fqdn == ""
    vcenter_fqdn = conn.host
  end
  session = sessionMgr.AcquireCloneTicket()
  thumbprint = Digest::SHA1.hexdigest(conn.http.peer_cert.to_der).upcase
  thumbprintParts = thumbprint.split(//)
  thumbprint = []
  while thumbprintParts.length > 0
    thumbprint << thumbprintParts.shift(2).join("")
  end
  thumbprint = thumbprint.join(":")

  $rvc_vmrc_ver_urls ||= {}
  $rvc_vmrc_ver_urls['5.5.0'] = '/console/'

  vmsProps = pc.collectMultiple(vms, 'name')
  vms.each do |vm|
    vmName = vmsProps[vm]['name']
    if !opts[:no_html5]
      if ver < "5.5.0"
        err "VC older than 5.5 doesn't support HTML5 client. Try --no-html5"
      else
        path = $rvc_vmrc_ver_urls[ver]
        url = "https://#{conn.host}:#{htmlPort}#{path}?vmId="
        url += "#{vm._ref}&vmName=#{vmName}&serverGuid=#{server_guid}&host=#{vcenter_fqdn}:443&sessionTicket=#{session}&thumbprint=#{thumbprint}"
      end
    else
      if ver < "5.0.0"
        err "VC is older than 5.0. Not supported by this command"
      elsif ['5.0.0'].member?(ver)
        url = "https://#{conn.host}:9443/vsphere-client/vmrc/vmrc.jsp"
        url += "?vm=#{vcUuid}:VirtualMachine:#{vm._ref}"
      else # ['5.1.0', '5.5.0'].member?(ver)
        url = "https://#{conn.host}:9443/vsphere-client/vmrc/vmrc.jsp"
        url += "?vm=urn:vmomi:VirtualMachine:#{vm._ref}:#{vcUuid}"
      end
    end
    puts "#{vmsProps[vm]['name']}: #{url}"
  end
end
