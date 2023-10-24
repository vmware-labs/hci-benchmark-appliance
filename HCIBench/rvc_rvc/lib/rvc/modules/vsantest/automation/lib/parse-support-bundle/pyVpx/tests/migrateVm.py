#!/usr/bin/python

"""
Script to migrate or clone a VM from one vCenter to another within
a linked group. The destination vCenter will be looked up from the
service directory of the source vCenter by the given host name.
"""

from __future__ import print_function

from pyVim import connect, task, invt, vimutil
from pyVmomi import Vim
from pyVmomi.VmomiSupport import newestVersions
from vimsupport import VimSession, CreateSession
import vimsupport
import sys, os, getopt, time

def Usage(msg=None):
   scriptName = os.path.basename(os.path.splitext(__file__)[0])
   if msg != None:
      print("%s" % msg)
   print("Usage: %s [options]" % scriptName)
   print("\n  %s\n" % __doc__.strip())
   print("Options:")
   print("  --server, VC server to connect to (default localhost)")
   print("  --user, VC User name to connect as (default "
         "Administrator@vsphere.local)")
   print("  --pwd, VC User password (default Admin!23)")
   print("  --remote, remote VC to connect to (optional defaults to same vc)")
   print("  --ruser, Remote VC User name to connect as (default "
         "Administrator@vsphere.local)")
   print("  --rpwd, Remote VC User password (default Admin!23)")
   print("  --vm, VM to be migrated (required)")
   print("  --diskKey, key of the disk to be migrated to (optional)")
   print("  --folder, dest folder where the VM to be migrated to (optional)")
   print("  --host, dest ESX host where the VM to be migrated to (required)")
   print("  --datastore, dest datastore the VM is to be migrated to (required)")
   print("  --diskDatastore, dest datastore where the disk (specified with "
         "diskKey) be migrated to (optional)")
   print("  --vmProfileId, dest vm profile Id (optional)")
   print("  --diskProfileId, dest disk profile Id (optional)")
   print("")
   exit()

def RelocateVm(session, vm, spec):
   print("Relocating VM '%s' with spec %s\n" % (vm.GetName(), spec))
   t = vm.Relocate(spec)
   try:
      result = session.WaitForTask(t)
   except Exception as e:
      print("Relocate VM task failed: %s" % e)
      return

def main():
   server = 'localhost'
   user = 'Administrator@vsphere.local'
   pwd = 'Admin!23'
   remote = None
   ruser = None
   rpwd = None
   vmName = None
   folderName = None
   hostName = None
   dsName = None
   diskKey = 0
   diskDsName = None
   vmProfileId = None
   diskProfileId = None

   try:
     opts,args = getopt.getopt(sys.argv[1:], '',
                               ['vm=', 'server=', 'user=', 'pwd=',
                               'remote=', 'ruser=', 'rpwd=',
                               'host=', 'datastore=', 'folder=',
                               'diskKey=', 'diskDatastore=',
                               'vmProfileId=', 'diskProfileId='])
   except getopt.GetoptError:
     Usage()
     print("getopt failed: " % getopt.GetoptError)

   for a,v in opts:
      if a == '--server':
         server = v
      if a == '--user':
         user = v
      if a == '--pwd':
         pwd = v
      if a == '--remote':
         remote = v
      if a == '--ruser':
         ruser = v
      if a == '--rpwd':
         rpwd = v
      if a == '--vm':
         vmName = v
      if a == '--folder':
         folderName = v
      if a == '--host':
         hostName = v
      if a == '--diskKey':
         diskKey = int(v)
      if a == '--datastore':
         dsName = v
      if a == '--diskDatastore':
         diskDsName = v
      if a == '--vmProfileId':
         vmProfileId = v
      if a == '--diskProfileId':
         diskProfileId = v

   if ruser == None:
      ruser = user

   if rpwd == None:
      rpwd = pwd

   if vmName == None:
      Usage('Required option vm is not supplied')

   if hostName == None:
      Usage('Required option host is not supplied')

   if dsName == None:
      Usage('Required option datastore is not supplied')

   vimNs = newestVersions.GetWireId('vim')
   session = CreateSession(server, '443', user, pwd, vimNs)
   vm = session.GetVM(vmName)
   if vm is None:
      print("Cannot find VM with name (%s)" % vmName)
      return

   spec = Vim.Vm.RelocateSpec()
   rsession = session
   if remote:
      try:
         rsession = CreateSession(remote, '443', ruser, rpwd, vimNs)
      except Exception as e:
         print("Failed to connect to %s: %s" % (remote, e))

      locator = vimutil.GetServiceLocator(rsession.si, ruser, rpwd)
      if locator is None:
         print("Cannot find service locator for %s " % remote)
         return
      spec.SetService(locator)

   host = rsession.GetHost(hostName)
   if host != None:
      if folderName != None:
         spec.SetFolder(rsession.GetFolder(folderName))
      else:
         spec.SetFolder(rsession.GetDatacenter().GetVmFolder())
      spec.SetHost(host)
      spec.SetPool(host.GetParent().GetResourcePool())
      spec.SetDatastore(rsession.GetDatastore(host, dsName))

   if spec.GetHost() is None:
      print("Cannot find host (%s) " % hostName)
      return

   if spec.GetDatastore() is None:
      print("Host (%s) does not have datastore (%s)" % (hostName, dsName))
      return

   if vmProfileId != None:
      vmProfileSpecs = []
      vmProfileSpec = Vim.Vm.DefinedProfileSpec()
      vmProfileSpec.profileId = vmProfileId
      vmProfileSpecs.append(vmProfileSpec)
      spec.SetProfile(vmProfileSpecs)

   if diskKey != 0:
      diskLocators = []
      diskLoc = Vim.Vm.RelocateSpec.DiskLocator()
      diskLoc.diskId = diskKey
      if diskDsName != None:
         diskLoc.SetDatastore(rsession.GetDatastore(host, diskDsName))
      if diskProfileId != None:
         diskProfileSpecs = []
         diskProfileSpec = Vim.Vm.DefinedProfileSpec()
         diskProfileSpec.profileId = diskProfileId
         diskProfileSpecs.append(diskProfileSpec)
         diskLoc.SetProfile(diskProfileSpecs)
      diskLocators.append(diskLoc)
      spec.SetDisk(diskLocators)

   print("start")
   RelocateVm(session, vm, spec)

if __name__ == "__main__":
   main()

