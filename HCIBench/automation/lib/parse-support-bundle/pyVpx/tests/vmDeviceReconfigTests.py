#!/usr/bin/python

import sys
import getopt
from pyVmomi import Vim
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm
from pyVim import vmconfig
from pyVim import arguments
from pyVim.helpers import Log,StopWatch
import soundcard
#import cdrom
#import serial
#import parallel
import floppy
import atexit

def EnumerateDevice(fn, dev):
   myList = fn()
   if myList == None:
      Log("No devices of type: " + dev)
      return 0
   else:
      itemListStr = ""
      for item in myList:
         if itemListStr != "":
            itemListStr = itemListStr + ", "
         itemListStr = itemListStr + item.GetName()
      Log(dev + " devices: " + itemListStr)
      return len(myList)

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd"),
                     (["v:", "vmname="], "BasicReconfigTest", "Name of the virtual machine", "vmname"),
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
                pwd=args.GetKeyValue("pwd"))
   atexit.register(Disconnect, si)

   # Process command line
   vmname = args.GetKeyValue("vmname")
   numiter = int(args.GetKeyValue("iter"))
   runall = args.GetKeyValue("runall")
   noDelete = args.GetKeyValue("nodelete")
   status = "PASS"

   try:
      # Enumerate devices
      target = vmconfig.GetCfgTarget(None)
      numSound = 0
      numFloppy = 0

      numSound = EnumerateDevice(target.GetSound, "Sound")
      EnumerateDevice(target.GetParallel, "Parallel")
      EnumerateDevice(target.GetSerial, "Serial")
      numFloppy = EnumerateDevice(target.GetFloppy, "Floppy")
      EnumerateDevice(target.GetCdRom, "Cdrom")

      for i in range(numiter):
         bigClock = StopWatch()
         vm1 = None
         try:
            vm1 = vm.CreateQuickDummy(vmname + "_" + str(i), 1)
            ### How can we combine very similar tests across multipe types
            ### of devices?

            if numFloppy == 0:
               Log("No floppies found. Skipping floppy tests")
            else:
               floppy.BasicCreateDelete(vm1)
               # These tests fail for as yet unknown reasons.
               #floppy.CreateFloppyRemoteWithAutoDetect(vm1, True)
               #floppy.CreateFloppyRemoteWithAutoDetect(vm1, False)
               floppy.CreateFloppyDevWithAutoDetect(vm1, True)
               floppy.CreateFloppyDevWithAutoDetect(vm1, False)
               floppy.CreateFloppyWithNoDeviceAndAutoDetect(vm1)
               floppy.CreateFloppyWithNoDeviceAndNoAutoDetect(vm1)
               floppy.EditFloppySetAndUnsetAutodetect(vm1)

            if numSound == 0:
               Log("No sound cards found. Skipping sound tests")
            else:
               soundcard.BasicCreateDelete(vm1)
               soundcard.CreateEnsoniqWithAutoDetect(vm1)
               soundcard.CreateEnsoniqWithNoAutoDetect(vm1)
               soundcard.CreateSB16WithAutoDetect(vm1)
               soundcard.CreateSB16NoAuto(vm1)
               soundcard.CreateSoundCardWithNoDeviceAndAutoDetect(vm1)
               soundcard.CreateSoundCardWithNoDeviceAndNoAutoDetect(vm1)
               soundcard.EditExistingEnsoniqToSetAndUnsetAutodetect(vm1)
               # This test fails since the current implementation overwrites
               # sound cards
               #CreateMultipleSoundCards(vm1)
               status = "PASS"
         finally:
            # Delete the vm as cleanup
            if noDelete == False:
               if vm1 != None:
                  task = vm1.Destroy()
                  WaitForTask(task)
            vm1 = None
            bigClock.finish("iteration " + str(i))
   except Exception as e:
      status = "FAIL"
      Log("Caught exception : " + str(e))

# Start program
if __name__ == "__main__":
    main()
