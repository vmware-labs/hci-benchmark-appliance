#!/usr/bin/python

from __future__ import print_function

import sys
from pyVmomi import Vim
from pyVmomi import Vmodl
from pyVmomi import VmomiSupport
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import invt
from pyVim import vm
from pyVim import vimutil
from time import sleep
import atexit

# Verify vm swap policy
def VerifySwapPlacementPolicy(vm1, policy):
    cfg = vm1.GetConfig()
    swapPolicy = cfg.GetSwapPlacement()
    if policy != None:
       if (swapPolicy != policy):
          print("Swap policy not set as expected; Expected: %s; "
                "Recieved: %s" % (policy, swapPolicy))
          raise "Failed to match policy"
    print("Swap policy set to %s" % swapPolicy)

# Change vm swap policy
def SetSwapPolicy(vm1, policy):
   cspec = Vim.Vm.ConfigSpec()
   cspec.SetSwapPlacement(policy)
   try:
      vimutil.InvokeAndTrack(vm1.Reconfigure, cspec)
   except Exception as e:
      raise

# Set host wide swap placement
def SetHostSwapPolicy(cr, policy = None, modify = True):
   cspec = Vim.ComputeResource.ConfigSpec()
   cspec.SetVmSwapPlacement(policy)
   try:
      vimutil.InvokeAndTrack(cr.ReconfigureEx, cspec, modify)
   except Exception as e:
      raise

# Verify host wide swap policy
def VerifyHostSwapPolicy(cr, policy):
   curr = cr.GetConfigurationEx().GetVmSwapPlacement()
   if policy != None:
      if (policy != curr):
         print("Host swap policy not set as expected; Expected: %s; "
               "Recieved: %s" % (policy, curr))
         raise "Failed to match host policy"
   print("Host policy set to %s" % curr)

# Verify host wide datastore location
def VerifyHostSwapLocation(hs, dsCheck = None, doCheck = True):
    ds = hs.GetConfig().GetLocalSwapDatastore()
    foundUrl = None
    if ds != None:
        foundUrl = ds.GetSummary().GetUrl()
    dsUrl = None
    if dsCheck != None:
        dsUrl = dsCheck.GetSummary().GetUrl()
    if doCheck == True:
        if (dsUrl != foundUrl):
            print("Host swap datastore not set as expected; Expect: %s; "
                  "Received: %s" % (dsUrl, foundUrl))
            raise "Failed to match host datastore"
    print("Host datastore is set to %s" % foundUrl)

# Set the host swap location datastore.
def SetHostSwapLocation(hs, dsRef):
    hs.GetConfigManager().GetDatastoreSystem().UpdateLocalSwapDatastore(dsRef)

def main():
    # Process command line
    host = "sandhyak-dev1.eng.vmware.com"
    if len(sys.argv) > 1:
       host = sys.argv[1]

    # Can be used to verify that the vmx file is changing appropriately.
    sleepInterval = 0

    # Connect
    si = Connect(host)
    atexit.register(Disconnect, si)

    cr = invt.GetHostFolder().GetChildEntity()[0]
    hs = cr.GetHost()[0]
    dsList = hs.GetConfigManager().GetDatastoreSystem().GetDatastore()
    if len(dsList) < 1:
        print("Cannot perform tests without at least one configured datastore")

    ##
    ## Host swap dir tests
    ##
    ## Check that host wide swap dir set/get works correctly
    ##
    ## XXX: Exercise to the user: Restart hostd and verify setting is picked up
    ## correctly. Verify that when the datastore specified is not present,
    ## vms behave reasonably (power on in the vmdirectory).
    ## Also, verify inaccessible datastores throw invalid argument.
    ##
    VerifyHostSwapLocation(hs, doCheck = False)

    SetHostSwapLocation(hs, dsList[0])
    VerifyHostSwapLocation(hs, dsList[0])

#    This test doesnt work (vmkernel update required)
#    SetHostSwapLocation(hs, None)
#    VerifyHostSwapLocation(hs, None)
    try:
        SetHostSwapPolicy(cr, "hostLocal")
    except Vmodl.Fault.InvalidArgument as e:
        print("Recieved invalid argument exception when setting host swap "
              "without host swap dir (good!)")

    SetHostSwapLocation(hs, dsList[0])
    VerifyHostSwapLocation(hs, dsList[0])


    ##
    ## Host swap policy tests
    ##
    ## Check that host wide enable/disable works
    ##
    ## XXX: Exercise to the user: Restart hostd and verify setting is picked up
    ## correctly.
    ##
    VerifyHostSwapPolicy(cr, None)

    # Set it to hostLocal
    SetHostSwapPolicy(cr, "hostLocal")
    VerifyHostSwapPolicy(cr, "hostLocal")
    sleep(sleepInterval)

    # Set it to vmDirectory
    SetHostSwapPolicy(cr, "vmDirectory")
    VerifyHostSwapPolicy(cr, "vmDirectory")
    sleep(sleepInterval)

    # Set it to inherit (this is invalid)
    try:
       SetHostSwapPolicy(cr, "inherit")
    except Vmodl.Fault.InvalidArgument as e:
       print("Received invalid argument exception setting host swap policy to "
             "inherit (good!)")

    # Set it to bogus value
    try:
       SetHostSwapPolicy(cr, "bogus")
    except Vmodl.Fault.InvalidArgument as e:
       print("Received invalid argument exception setting host swap policy to "
             "bogus (good!)")

    # Set it to hostLocal
    SetHostSwapPolicy(cr, "hostLocal")
    VerifyHostSwapPolicy(cr, "hostLocal")
    sleep(sleepInterval)

    # Reset to default
    SetHostSwapPolicy(cr, modify = False)
    VerifyHostSwapPolicy(cr, "vmDirectory")
    sleep(sleepInterval)

    # Set it to hostLocal
    SetHostSwapPolicy(cr, "hostLocal")
    VerifyHostSwapPolicy(cr, "hostLocal")
    sleep(sleepInterval)


    ##
    ## VM swap policy tests
    ##
    ## Check that VM specific policy changes take.
    ##
    ## XXX: Need to power on and verify settings take.
    ##
    # Create a test vm
    print("Creating test vm")
    vm1 = vm.CreateQuickDummy("CreateTest", 1)

    try:
       # Swap policy on a newly created vm
       VerifySwapPlacementPolicy(vm1, None)
       sleep(sleepInterval)

       # Set to inherit
       SetSwapPolicy(vm1, "inherit")
       VerifySwapPlacementPolicy(vm1, "inherit")
       sleep(sleepInterval)

       # Set to vmDirectory
       SetSwapPolicy(vm1, "vmDirectory")
       VerifySwapPlacementPolicy(vm1, "vmDirectory")
       sleep(sleepInterval)

       # Set to hostLocal
       SetSwapPolicy(vm1, "hostLocal")
       VerifySwapPlacementPolicy(vm1, "hostLocal")
       sleep(sleepInterval)

       # Dont change it and verify nothing happens
       SetSwapPolicy(vm1, None)
       VerifySwapPlacementPolicy(vm1, "hostLocal")
       sleep(sleepInterval)

       # Set it to bogus value
       try:
          SetSwapPolicy(vm1, "bogus")
       except Vmodl.Fault.InvalidArgument as e:
          print("Recieved invalid argument exception setting to bogus for vm (good!)")

       # Switch back to inherit
       SetSwapPolicy(vm1, "inherit")
       VerifySwapPlacementPolicy(vm1, "inherit")
       sleep(sleepInterval)

    finally:
       # Delete the vm
       print("Deleting test vm")
       task = vm1.Destroy()
       WaitForTask(task)


# Start program
if __name__ == "__main__":
    main()
