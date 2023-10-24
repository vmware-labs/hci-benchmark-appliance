#!/usr/bin/python

#
# Common utility methods for Guest Ops Tests.
#

import getopt
import time
import array
from pyVmomi import Vim, Vmodl
from pyVim.connect import SmartConnect
from pyVim.helpers import Log
from pyVim import folder
from pyVim import vm
from pyVim import task
from pyVim import connect
from optparse import OptionParser

#
# Common module for reading in command line options for tests.
# Please enhance this as needed for newer tests.
#

global npAuth
npAuth = Vim.Vm.Guest.NamePasswordAuthentication

def get_options():
   parser = OptionParser()
   parser.add_option("-H", "--host",
                     default="",
                     help="remote host to connect to")
   parser.add_option("-u", "--user",
                     default="root",
                     help="User name to use when connecting to hostd")
   parser.add_option("-p", "--password",
                     default="ca$hc0w",
                     help="Password to use when connecting to hostd")
   parser.add_option("-U", "--guestuser",
                     default="vmware",
                     help="Guest username")
   parser.add_option("-P", "--guestpassword",
                     default="vmware",
                     help="Guest password")
   parser.add_option("-R", "--guestrootuser",
                     default="",
                     help="Guest Root username")
   parser.add_option("-X", "--guestrootpassword",
                     default="",
                     help="Guest Root password")
   parser.add_option("-v", "--vmname",
                     default="",
                     help="Name of the virtual machine")
   parser.add_option("-V", "--vmxpath",
                     default="",
                     help="Datastore path to the virtual machine")
   (options, _) = parser.parse_args()
   return options


#
# Common module for initializing most tests.
#

def init(hostname, user, passwd, vmname, vmxpath, guestuser, guestpwd,
         guestrootuser, guestrootpassword, powerOn=True, getIntCont=False):
   # Connect and get the Service Instance.
   # Make sure we get the proper version (dev).
   svcInst = SmartConnect(host=hostname, user=user, pwd=passwd)
   svcInstIntCont = ""
   if getIntCont:
      svcInstIntCont = svcInst.RetrieveInternalContent()

   # Find the vm if it's there.
   virtualMachine = folder.Find(vmname)

   # if it's not there, maybe we just rebooted and it lost its config,
   # so try to register and re-find.
   if virtualMachine == None:
      Log("Registering " + vmxpath)
      folder.Register(vmxpath)
      virtualMachine = folder.Find(vmname)

   # set up a guest auth object with root privs
   guestAdminAuth = ""
   if guestrootuser != "":
      guestAdminAuth = npAuth(username=guestrootuser, password=guestrootpassword,
                              interactiveSession=False)

   # set up a guest auth object (good and bad)
   guestAuth = npAuth(username=guestuser, password=guestpwd, interactiveSession=False)

   guestAuthBad = npAuth(username="XXX", password="XXX", interactiveSession=False)

   # power on the VM if needed
   if powerOn and virtualMachine.GetRuntime().GetPowerState() != Vim.VirtualMachine.PowerState.poweredOn:
      Log("Powering on")
      vm.PowerOn(virtualMachine)

   if not getIntCont:
      globs = [svcInst, virtualMachine, guestAdminAuth, guestAuth, guestAuthBad]
   else:
      globs = [svcInst, svcInstIntCont, virtualMachine, guestAdminAuth, guestAuth, guestAuthBad]

   return globs

#
# Power Off a VM and wait for it to stop.
#

def powerOffVM(virtualMachine):
   vm.PowerOff(virtualMachine);
   while True:
      Log("Waiting for VM to get powered off");
      if virtualMachine.GetRuntime().GetPowerState() == Vim.VirtualMachine.PowerState.poweredOff:
         break
      time.sleep(3)


#
# Power On a VM and wait for it to start.
#

def powerOnVM(virtualMachine):
   vm.PowerOn(virtualMachine);
   while True:
      Log("Waiting for VM to get powered on");
      if virtualMachine.GetRuntime().GetPowerState() == Vim.VirtualMachine.PowerState.poweredOn:
         break
      time.sleep(3)

#
# guestops not ready test
#

def testNotReady(procMgr, virtualMachine, guestAuth):
   try:
      Log("Testing ListProcesses() before guestops are ready")
      pids = [123]
      result  = procMgr.ListProcesses(virtualMachine, guestAuth, pids)
      Log("Expected NOTREACHED -- but will pass if guestops are ready (%s)" % result)
   except Vim.Fault.GuestProcessNotFound as il:
      Log("Got expected (GuestProcessNotFound) fault")
   # Windows throws invalid arg if the pid is bad
   except Vmodl.Fault.InvalidArgument as il:
      Log("Got expected (InvalidArgument) fault")
   except Vim.Fault.GuestOperationsUnavailable as il:
      Log("Got expected (GuestOperationsUnavailable) fault")

#
# Wait for tools to start in the VM.
#

def waitForTools(virtualMachine):
   while True:
      Log("Waiting for guest operations")
      if virtualMachine.GetGuest().GetGuestOperationsReady():
         break
      time.sleep(3)
