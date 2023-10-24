#!/usr/bin/python

"""
Copyright 2013,2016 VMware, Inc.  All rights reserved. -- VMware Confidential

A set of tests that induces various vMotion failures, and checks
for proper error recovery.
"""
from __future__ import print_function

import sys
import os
import time
import getopt
import shutil
import traceback
from pyVmomi import vim, vmodl
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim.helpers import Log
from pyVim import vm
from pyVim import vmconfig
from pyVim import host
from pyVim import invt
from pyVim import connect
from pyVim import arguments
from pyVim import folder
from pyVim import path

status = "PASS"
PowerState = vim.VirtualMachine.PowerState

def IsTestEsx():
    """
    Returns True iff the current invocation is running under test-esx.
    """

    return 'TESTESX_VOLUME' in os.environ

def GetDatastore(si, name):
    """
    Returns the non-UUID datastore name for the supplied name.

    The supplied name is a string that specifies the datastore.  It is
    either a UUID or non-UUID name.  This function will do the
    conversion from UUID to non-UUID name if necessary, as well as
    validate that the datastore actually exists.
    """

    hs = host.GetHostSystem(si)
    datastores = hs.GetDatastore()
    name = name.replace('/vmfs/volumes/', '')
    for ds in datastores:
        if (ds.name == name or
            ds.info.url.replace('/vmfs/volumes/', '') == name):
           return ds.name
    raise Exception('Error looking up datastore: %s' % name)

def CleanDirs(si, dsName, vmName):
    """
    Remove directories created by test.
    """
    Log('Cleaning up %s on %s' % (vmName, dsName))
    CleanupDir(dsName, vmName)

def CleanupDir(datastoreName, folderName):
   si = connect.GetSi()
   fileMgr = si.content.fileManager
   try:
      WaitForTask(fileMgr.Delete(datastorePath="[%s] %s" %
                                 (datastoreName, folderName),
                                 fileType=vim.FileManager.FileType.File))
   except vim.fault.FileNotFound as e:
       pass
   except Exception as e:
      Log("Error cleaning up %s: %s" % (folderName, e))

def CleanupVm(vmname, useLlpm = False):
    if isinstance(vmname, vim.VirtualMachine):
       Log("Cleaning up VMs with name %s" % vmname.name)
       oldVms = [vmname]
    else:
       Log("Cleaning up VMs with name %s" % vmname)
       oldVms = folder.FindPrefix(vmname)
    for oldVm in oldVms:
       if oldVm.GetRuntime().GetPowerState() == PowerState.poweredOn:
          vm.PowerOff(oldVm)
       Log("Destroying VM")
       if useLlpm == True:
          vmConfig = oldVm.GetConfig()
          llpm = invt.GetLLPM()
          llpm.DeleteVm(vmConfig)
       else:
          vm.Destroy(oldVm)

def ReportFiles(path):
    """
    Report VM files sitting in the given directory.

    Only useful when running under test-esx.
    """

    def Blacklisted(name):
        blacklist = '.vmdk .vswp .nvram .hlog .lck'.split()
        for j in blacklist:
            if j in name:
                return True
        return False

    for i in os.listdir(path):
        i = os.path.join(path, i)
        if not os.path.isfile(i) or Blacklisted(i):
            continue
        print('#BUGREPORT:LOGFILE:%d# %s' % (os.getppid(), i))

class TestVmx(object):
   def __init__(self, src, dst):
      self.src = src
      self.dst = dst
      if not self.name:
         raise Exception("Test must have a name")
   def __str__(self):
      return self.name
   def setup(self):
     # Dest VM needs to have a VPD value matching the source
     opt = vim.Option.OptionValue()
     opt.SetKey("numa.autosize.vcpu.maxPerVirtualNode")
     opt.SetValue("1")
     extraCfgs = self.dst.GetConfig().GetExtraConfig()
     extraCfgs.append(opt)
     cSpec = vim.Vm.ConfigSpec()
     cSpec.SetExtraConfig(extraCfgs)
     WaitForTask(self.dst.Reconfigure(cSpec))
   def cleanup(self):
      pass
   def gotSuccess(self):
      pass
   def gotFailure(self, e):
      raise e

class TestVmxFail(TestVmx):
   def __init__(self, src, dst):
      TestVmx.__init__(self, src, dst)
      self.option = 'vmx.test.migrate.fail.%s' % self.name
   def setup(self):
     TestVmx.setup(self)
     opt = vim.Option.OptionValue()
     opt.SetKey(self.option)
     opt.SetValue("TRUE")
     for v in [self.src, self.dst]:
        # Configure failure point. (Source & Dest)
        Log("Reconfiguring %s for '%s' failure" % (str(v), self.name))
        extraCfgs = v.GetConfig().GetExtraConfig()
        extraCfgs.append(opt)
        cSpec = vim.Vm.ConfigSpec()
        cSpec.SetExtraConfig(extraCfgs)
        WaitForTask(v.Reconfigure(cSpec))
   def cleanup(self):
      # Unconfigure failure point. (Source only; Dest is not re-used)
      Log("Reconfiguring to remove '%s' failure" % self.name)
      extraCfgs = self.src.GetConfig().GetExtraConfig()
      for opt in extraCfgs:
         if opt.GetKey() == self.option:
            opt.SetValue("")
      cSpec = vim.Vm.ConfigSpec()
      cSpec.SetExtraConfig(extraCfgs)
      WaitForTask(self.src.Reconfigure(cSpec))
   def gotSuccess(self):
      raise Exception("Did not hit exception as expected")
   def gotFailure(self, e):
      expectedMsg = "Migrate failure due to instrumentation during %s." % self.name
      if expectedMsg in str(e):
         Log("Caught exception as expected")
      else:
         raise e

class TestVmxSuccess(TestVmx):
   name = 'success'
   def cleanup(self):
      vm.PowerOff(self.dst)
      TestVmx.cleanup(self)
class TestVmxFailTo(TestVmxFail):
   name = 'to'
class TestVmxFailToEvent(TestVmxFail):
   name = 'toEvent'
class TestVmxFailInit(TestVmxFail):
   name = 'init'
   globalConfig = '/etc/vmware/config'
   def setup(self):
      TestVmxFail.setup(self)
      shutil.copy2(self.globalConfig, self.globalConfig + '_bk')
      with open(self.globalConfig, 'a') as f:
         f.write('init.forceFail = "Sig"\n')
      self._tSetupDone = time.perf_counter()
   def gotFailure(self, e):
      shutil.move(self.globalConfig + '_bk', self.globalConfig)
      elapsed = time.perf_counter() - self._tSetupDone
      if not isinstance(e, vmodl.Fault.SystemError):
         raise e
      if elapsed > 60:
         raise Exception("Took unexpectedly long (%f s) to get failure" %
                         elapsed)
      Log("Caught exception as expected")
   def gotSuccess(self):
      shutil.move(self.globalConfig + '_bk', self.globalConfig)
      TestVmxFail.gotSuccess(self)
   def cleanup(self):
      Log("Waiting 2 minutes for source to time out")
      time.sleep(2 * 60)
      TestVmxFail.cleanup(self)
class TestVmxFailFrom(TestVmxFail):
   name = 'from'
   def cleanup(self):
      # Source doesn't know dest failed, and exposes no APIs for pyVim
      # to cancel any earlier. So we get to wait 4 minutes (default timeout).
      Log("Waiting 4 minutes for source to time out")
      time.sleep(4 * 60)
      TestVmxFail.cleanup(self)
class TestVmxFailPrepareDst(TestVmxFail):
   name = 'prepareDst'
   def setup(self):
      TestVmxFail.setup(self)
      self._tSetupDone = time.perf_counter()
   def gotFailure(self, e):
      elapsed = time.perf_counter() - self._tSetupDone
      if not isinstance(e, vim.Fault.Timedout):
         raise e
      if elapsed > 5.5 * 60:
         raise Exception("Took unexpectedly long (%f s) to get Timedout" %
                         elapsed)
      Log("Caught exception as expected")
   def cleanup(self):
      # Wait for dest vmx to idle timeout (5 minutes - 2 minutes of GetWid wait)
      Log("Waiting 3 minutes for dest vmx to time out")
      time.sleep(3 * 60)
      TestVmxFail.cleanup(self)
class TestVmxFailStart(TestVmxFail):
   name = 'start'
   def gotFailure(self, e):
      # Even though the source reports a fault with TestVmxFail's pattern,
      # VMotionManager prefers to report the destination's timeout error.
      # Note that it takes 2 minutes (default timeout) before this gets thrown.
      expectedMsg = "The vMotion failed because the destination host did not receive data"
      if expectedMsg in str(e):
         Log("Caught exception as expected")
      else:
         raise e

def main():
   global status
   supportedArgs = [ (["H:", "host="], "localhost", "Host name", "host"),
                     (["k:", "keep="], "0", "Keep configs", "keep"),
                     (["e:", "useExisting="], False, "Use existing VM", "useExistingVm"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["v:", "VM name="], "vmotionErrs", "Name of the virtual machine", "vmname"),
                     (["d:", "dsName="], None, "Target datastore for storage VMotions", "dsName"),
                     (["i:", "numiter="], "1", "Number of iterations", "iter"),
                   ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage"),
                      ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   # Process command line
   host = args.GetKeyValue("host")
   vmname = args.GetKeyValue("vmname")
   numiter = int(args.GetKeyValue("iter"))
   keep = int(args.GetKeyValue("keep"))
   useExistingVm = bool(args.GetKeyValue("useExistingVm"))
   dsName = args.GetKeyValue("dsName")

   for i in range(numiter):
       si = None
       try:
           # Connect to host
           si = SmartConnect(host=host,
                             user=args.GetKeyValue("user"),
                             pwd=args.GetKeyValue("pwd"))
           Log("Connected to Host")

           dsName = GetDatastore(si, dsName)
           Log('Using datastore: %s' % dsName)

           # Cleanup from previous runs
           if not useExistingVm:
               CleanupVm(vmname)
               CleanDirs(si, dsName, vmname)

           # Create new VM
           connect.SetSi(si)
           theVm = None
           if useExistingVm:
               theVm = folder.Find(vmname)
               if theVm == None:
                   raise Exception("No VM with name %s found!" % vmname)
               Log("Using VM %s" % vmname)
           else:
               Log("Creating VM %s" % vmname)
               # Short delay to avoid colliding with a cleanup.
               time.sleep(1)
               # XXX numScsiDisks=0. vm.Migrate() doesn't know about
               # xvmotion, so it fails to set up the disk copy spec
               theVm = vm.CreateQuickDummy(vmname,
                                           guest="winXPProGuest",
                                           memory=4,
                                           cdrom=0,
                                           numScsiDisks=0,
                                           datastoreName=dsName)

           if theVm.GetRuntime().GetPowerState() == PowerState.poweredOff:
              Log("Powering on VM.")
              vm.PowerOn(theVm)
           else:
              Log("VM already powered on.")

           srcDir = os.path.dirname(theVm.config.files.vmPathName)

           tests = [
              TestVmxFailTo,
              TestVmxFailToEvent,
              TestVmxFailInit,
              TestVmxFailFrom,
              TestVmxFailPrepareDst,
              TestVmxFailStart,
              TestVmxSuccess,    # Must be last: does not switch back to source
           ]
           for testClass in tests:
              Log("Creating dummy dest")
              dstPath = os.path.join(srcDir, testClass.name, vmname + ".vmx")
              dummySpec = vm.CreateQuickDummySpec(vmname,
                                                  guest="winXPProGuest",
                                                  memory=4,
                                                  cdrom=0,
                                                  numScsiDisks=0,
                                                  datastoreName=dsName)
              dummySpec.GetFiles().SetVmPathName(dstPath)
              dstVm = vm.CreateFromSpec(dummySpec)

              # Core of running an individual test
              theTest = testClass(theVm, dstVm)
              theTest.setup()
              Log("Attempt to vMotion with test '%s'" % str(theTest))
              try:
                 vm.Migrate(theVm, si, si, vmotionType='vmotion',
                            unsharedSwap=True,
                            dstPath=dstPath)
              except Exception as e:
                 theTest.gotFailure(e)
              else:
                 theTest.gotSuccess()
              theTest.cleanup()

           if not useExistingVm:
              CleanupVm(vmname)
       except Exception as e:
           Log("Caught exception : %s" % e)
           excType, excValue, excTB = sys.exc_info()
           stackTrace = " ".join(traceback.format_exception(
                                 excType, excValue, excTB))
           Log(stackTrace)
           status = "FAIL"
           Disconnect(si)
           if IsTestEsx():
               ReportFiles('/vmfs/volumes/%s/%s' % (dsName, vmname))
           return
       if status == "PASS" and IsTestEsx() and 'test-esx-vmotionErrs' in vmname:
           CleanDirs(si, dsName, vmname)
       Disconnect(si)

# Start program
if __name__ == "__main__":
    main()
    Log("Test status: %s" % status)
    Log("Migrate failure tests completed")
    if status != "PASS":
        sys.exit(1)
