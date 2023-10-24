#!/usr/bin/python

import sys
import time
import getopt
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm, folder
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import atexit

#
# Helper routine to add serial port with specified backing to a VM
#
def TestAddSerial(vm1, backingType):
   cspec = Vim.Vm.ConfigSpec()
   if backingType == Vim.Vm.Device.VirtualSerialPort.FileBackingInfo:
       cspec = vmconfig.AddFileBackedSerial(cspec, fileName = "[] /tmp/foo")
   elif backingType == Vim.Vm.Device.VirtualSerialPort.PipeBackingInfo:
       cspec = vmconfig.AddPipeBackedSerial(cspec, pipeName = "foo")
   elif backingType == Vim.Vm.Device.VirtualSerialPort.URIBackingInfo:
       cspec = vmconfig.AddURIBackedSerial(cspec, serviceURI = "tcp://service-host",
                                           direction = "server", proxyURI = "telnet://proxy-box")
   else:
       cspec = vmconfig.AddDeviceBackedSerial(cspec)

   vm.Reconfigure(vm1, cspec)
   devices = vmconfig.CheckDevice(vm1.GetConfig(),
                                  Vim.Vm.Device.VirtualSerialPort)
   for device in devices:
       if isinstance(device.backing, backingType):
           return
   raise Exception("Failed to find added serial port in VM's config")


def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmname="], "SerialPortTest", "Name of the virtual machine", "vmname"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter") ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage"),
                        (["runall", "r"], True, "Run all the tests", "runall"),
                        (["nodelete"], False, "Dont delete vm on completion", "nodelete") ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Connect
   si = Connect(host=args.GetKeyValue("host"),
                user=args.GetKeyValue("user"),
                pwd=args.GetKeyValue("pwd"),
                version="vim.version.version9")
   atexit.register(Disconnect, si)


   # Process command line
   vmname = args.GetKeyValue("vmname")
   numiter = int(args.GetKeyValue("iter"))
   runall = args.GetKeyValue("runall")
   noDelete = args.GetKeyValue("nodelete")
   status = "PASS"

   for i in xrange(numiter):
       bigClock = StopWatch()
       vm1 = None
       try:
           Log("Cleaning up VMs from previous runs...")
           vm.Delete(vmname, True)

           Log("Creating VM..")
           vm1 = vm.CreateQuickDummy(vmname)

           Log("Adding serial port with device backing")
           TestAddSerial(vm1, Vim.Vm.Device.VirtualSerialPort.DeviceBackingInfo)

           Log("Adding serial port with file backing")
           TestAddSerial(vm1, Vim.Vm.Device.VirtualSerialPort.FileBackingInfo)

           Log("Adding serial port with pipe backing")
           TestAddSerial(vm1, Vim.Vm.Device.VirtualSerialPort.PipeBackingInfo)

           Log("Adding serial port with URI backing")
           TestAddSerial(vm1, Vim.Vm.Device.VirtualSerialPort.URIBackingInfo)

           Log("Deleting VM..")
	   vm.Delete(vmname, True)

           Log("Tests completed.")
           bigClock.finish("iteration " + str(i))
       except Exception as e:
           status = "FAIL"
           Log("Caught exception : " + str(e))
   Log("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()

