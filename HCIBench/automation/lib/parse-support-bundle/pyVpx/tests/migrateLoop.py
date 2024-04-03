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

vimInternalNs = newestVersions.GetInternalNamespace('vim')

def RelocateVm(session, vm, spec):
   print("Relocating VM '%s' with spec %s\n" % (vm.GetName(), spec))
   t = vm.Relocate(spec)
   try:
      result = session.WaitForTask(t)
   except Exception as e:
      print("Relocate VM task failed: %s" % e)
      return

def Relocate(server, remote, hostName, dsName, vmName):
   user = 'root'
   pwd =  'vmware'
   folderName = None
   session = CreateSession(server, '443', user, pwd, vimInternalNs)
   vm = session.GetVM(vmName)
   if vm is None:
      print("Cannot find VM with name (%s)" % vmName)
      return

   rsession = session
   spec = Vim.Vm.RelocateSpec()
   if remote:
      try:
         rsession = CreateSession(remote, '443', user, pwd, vimInternalNs)
      except Exception as e:
         print("Failed to connect to %s: %s" % (remote, e))

      locator = vimutil.GetServiceLocator(rsession.si, user, pwd)
      if locator is None:
         print("Cannot find service locator for %s " % remote)
         return
      spec.SetService(locator)

   host = rsession.GetHost(hostName)
   if host is None:
      print("Cannot find host (%s) " % hostName)
      return

   spec.SetFolder(rsession.GetDatacenter().GetVmFolder())
   spec.SetHost(host)
   spec.SetPool(host.GetParent().GetResourcePool())
   spec.SetDatastore(rsession.GetDatastore(host, dsName))

   if spec.GetDatastore() is None:
      print("Host (%s) does not have datastore (%s)" % (hostName, dsName))
      return

   RelocateVm(session, vm, spec)
   return

def main():
   for i in range(1,10):
      Relocate(server='10.20.104.37', remote='10.20.104.139', hostName='10.20.105.11', dsName="NewDatastore (1)", vmName='xvc-demo-vm')
      Relocate(server='10.20.104.139', remote='10.20.104.37', hostName='10.20.104.146', dsName='NewDatastore', vmName='xvc-demo-vm')

if __name__ == "__main__":
   main()

