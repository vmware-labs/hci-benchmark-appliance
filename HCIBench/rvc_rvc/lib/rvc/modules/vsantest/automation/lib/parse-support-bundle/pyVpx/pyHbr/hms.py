#
# pyHbr.hms.py
#
# General functions useful for deploying the HMS appliance.
#

from pyHbr.util import GetBuild
from pyHbr.ovflib import OVFManagerDeployment

def GetOvfURL(buildID=None, branch='vr-2016', kind='ob'):
   build = GetBuild('hms-va', buildID, branch, kind)
   return build._buildtree_url + '/publish/ovf/vSphere_Replication_AddOn_OVF10.ovf'

class HMSOVFDeployment(OVFManagerDeployment):
   """OVF deployment for the HMS virtual appliance.

   Uses the OvfManager to deploy the appliance.
   """

   def __init__(self,
                ovfUrl,
                hostd,
                defaults=True):
      OVFManagerDeployment.__init__(self, ovfUrl, hostd, defaults)

      if defaults:
         self.SetProperty('enable_sshd', 'True')
         self.SetProperty('varoot-password', 'vmware11')
         self.SetProperty('vaadmin-password', 'vmware11')

      #
      # These are needed so that VAMI correctly detects that it should
      # use DHCP. It is assumed that this OVF deployment is being done
      # directly to the host.
      #
      self.SetProperty('vami.ip0.vSphere_Replication_Appliance', '')
      self.SetProperty('vami.netmask0.vSphere_Replication_Appliance', '')
      self.SetProperty('vami.gateway.vSphere_Replication_Appliance', '')
      self.SetProperty('vami.DNS.vSphere_Replication_Appliance', '')
      self.SetProperty('vm.vmname', 'vSphere_Replication_Appliance')

   def SetNetworkInfo(self, ip, netmask, gateway, dns):
      """Set the network details.

      Implicitly sets the IP allocation policy and protocol.
      """
      self.SetIpAllocationPolicy('fixedPolicy')

      # use inet_pton to check the type of the IP address
      try:
         socket.inet_pton(socket.AF_INET6, ip)
         self.SetIpProtocol('IPv6')
      except socket.error as e:
         socket.inet_pton(socket.AF_INET, ip)
         self.SetIpProtocol('IPv4')

      self.SetProperty('vami.ip0.vSphere_Replication_Appliance', ip)
      self.SetProperty('vami.netmask0.vSphere_Replication_Appliance', netmask)
      self.SetProperty('vami.gateway.vSphere_Replication_Appliance', gateway)
      self.SetProperty('vami.DNS.vSphere_Replication_Appliance', ','.join(dns))

   def SetSSHPassword(self, password):
      """Set the default SSH password for the appliance."""
      self.SetProperty('varoot-password', password)
      self.SetProperty('vaadmin-password', password)
