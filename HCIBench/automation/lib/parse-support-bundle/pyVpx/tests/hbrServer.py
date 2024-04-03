#!/usr/bin/python
#
# hbrServer.py
#
# Simple regression tests for the HBR server
#
# XXX Rename hbrsrvTestAlone.py?  XXX something better than that?
#

#
# To Use this script:
#
# (1) You must build the "vmodl-hbr-py-build" target.
# (2) Use the vim/py/py.sh wrapper script to run this:
#     bora/vim/py/py.sh bora/vim/py/tests/hbrServer.py
#

#
# Generated python wrappers for the Hbr.Replica VMODL (used by hbrsrv)
# are in:
#  build/build/vmodl/obj/generic/pyVmomi/_bindings_hbr.py
#


#
# TODO:
#  - run different tests from command line to make failure isolation easier
#
from __future__ import print_function

import sys
import random
import traceback
import atexit
import os
import tempfile
import re
import commands
import time
import httplib
import copy

from pyVmomi import Hbr
from pyVmomi import Vmodl # XXX for exceptions
#import pyVim
from pyVim.helpers import Log
from pyVim import arguments

import pyHbr.servercnx
import pyHbr.disks


# XXX ugly, but a side-effect of having factored these routines out of
# here originally
from pmtest import TestFunc, TestFailedExc, ExpectCond, \
     ExpectedException, ExpectException, ExpectNoException, \
     ExpectNotImplemented, ExpectNotFound, ExpectManagedObjectNotFound, \
     RunCommand


def CreateRandomId(prefix):
   return "%s-%u" % (prefix, random.randrange(0,1000*1000*1000))


def CreateRandomReplicaDiskPath():
   """
   Random relative path to a replica disk.  (No datastore component.)
   """
   global testdir

   vmdkName = CreateRandomId("hbrServer-disk") + ".vmdk"

   return os.path.join(testdir, vmdkName)


def CreateRandomVMPath():
   """
   Random relative path to a vm replica.  (No datastore component.)
   """

   global testdir

   vmdirName = CreateRandomId("vmcfg")

   return os.path.join(testdir, vmdirName)


allDisks = dict()


def CreateDisk(diskName, datastoreMgr):
   global defaultDsMgr
   global allDisks

   if (datastoreMgr == None):
      datastoreMgr = defaultDsMgr

   # only create a new disk if its really needed
   if not diskName in allDisks:
      datastoreMgr.CreateDisk(diskName)
      atexit.register(datastoreMgr.DeleteDisk, diskName)
      allDisks[diskName] = 0

   # ref count uses of disk
   allDisks[diskName] = allDisks[diskName] + 1


def CleanupDisk(diskName):
   global defaultDsMgr
   global allDisks

   if diskName in allDisks:
      allDisks[diskName] = allDisks[diskName] - 1
      if allDisks[diskName] == 0:
         defaultDsMgr.DeleteDisk(diskName)
         del allDisks[diskName]


def CreateDiskSpec(diskName,
                   diskRDID,
                   datastoreMgr):
   global defaultDsMgr
   if (datastoreMgr == None):
      datastoreMgr = defaultDsMgr

   vmfsPath = datastoreMgr.VMFSPath(diskName)

   # Create the diskIdent for the random location
   diskIdent = Hbr.Replica.IdentSpec()
   diskIdent.id = diskRDID
   diskIdent.datastoreUUID = datastoreMgr.DatastoreUUID()
   diskIdent.pathname = diskName + ".vmdk"

   # Actually create a disk:
   CreateDisk(vmfsPath, datastoreMgr)

   # Make a disk spec:
   disk = Hbr.Replica.DiskSpec()
   disk.diskIdent = diskIdent

   return disk


def CreateRandomizedDiskSpec(datastoreMgr):
   """
   Create a randomish disk spec for attaching to a group spec.

   Disk id is a random ID with the 'disk-id' prefix,
   """
   global defaultDsMgr
   if (datastoreMgr == None):
      datastoreMgr = defaultDsMgr

   diskName = CreateRandomReplicaDiskPath()
   diskRDID = CreateRandomId("disk-id")

   # Create disk with random name and ID:
   return CreateDiskSpec(diskName, diskRDID, datastoreMgr)


def CreateRandomizedVMIdent(datastoreMgr,
                            vmID=None):
   global defaultDsMgr
   if (datastoreMgr == None):
      datastoreMgr = defaultDsMgr

   if vmID is None:
      vmID = CreateRandomId("random-vm-id")

   # Random VM config directory location:
   vmPath = CreateRandomVMPath()
   vmfsPath = datastoreMgr.VMFSPath(vmPath)

   # Make the VM directory.  Needed by unconfigure tests, at least
   datastoreMgr.MakeDirectory(vmfsPath);

   # Fill out identity with vmID and location:
   vmIdent = Hbr.Replica.IdentSpec()
   vmIdent.id = vmID
   vmIdent.datastoreUUID = datastoreMgr.DatastoreUUID()
   vmIdent.pathname = vmPath

   return vmIdent


def CreateRandomizedVMSpec(datastoreMgr,
                           vmID=None,
                           diskCt=None):

   # Random number of disks attached to a random vm:
   diskCt = diskCt or random.randrange(0,6)

   # Random VM spec with random number of disks:
   vm = Hbr.Replica.VirtualMachineSpec()
   vm.virtualMachineIdent = CreateRandomizedVMIdent(datastoreMgr, vmID)
   vm.replicatedDisks = [ CreateRandomizedDiskSpec(datastoreMgr) for x in xrange(diskCt) ]

   return vm


def AddTierToRetentionPolicy(retentionPolicy,
                             granularityMins,
                             numSlots):
   newPolicy = retentionPolicy
   tier = Hbr.Replica.RetentionPolicy.Tier()
   tier.SetGranularityMinutes(int(granularityMins))
   tier.SetNumSlots(int(numSlots))
   if not newPolicy:
      newPolicy = Hbr.Replica.RetentionPolicy()
   if not newPolicy.tiers:
      newPolicy.tiers = [];
   newPolicy.tiers.append(tier)
   return newPolicy


def RetentionPolicyToString(retentionPolicy):
   policyString = ""
   if retentionPolicy != None and retentionPolicy.tiers != None:
      for tier in retentionPolicy.tiers:
         tier = str(tier.GetGranularityMinutes()) + "," + str(tier.GetNumSlots())
         policyString = policyString + "(" + tier + ")"
   return policyString


def CreateRandomizedGroupSpec(groupID=None,
                              rpo=None,
                              datastoreMgr=None,
                              retentionPolicy=None):

   if groupID is None:
      groupID = CreateRandomId("random-group-id")

   # Create one random VM spec:
   vm = CreateRandomizedVMSpec(datastoreMgr,vmID=groupID)

   # Put the VM spec in a simple random group spec:
   gspec = Hbr.Replica.GroupSpec()
   gspec.id = groupID
   gspec.rpo = rpo or random.randrange(1, 24*60)
   gspec.vms = [ vm, ]
   gspec.retentionPolicy = retentionPolicy or AddTierToRetentionPolicy(
                                             None,
                                             random.randrange(gspec.rpo, 24*60),
                                             random.randrange(1, 24))

   return gspec


def CreateInvalidGroupSpec(groupID,
                           disks,
                           datastoreMgr=None):

   Log("Spec '" +groupID+ "' w/disks: " +str(disks))

   # Make a VM spec with the virtual disks specified in *disks
   vm = Hbr.Replica.VirtualMachineSpec()
   vm.virtualMachineIdent = CreateRandomizedVMIdent(datastoreMgr, vmID=groupID)
   vm.replicatedDisks = [ ]

   # Convert variable number of name/rdid pairs into disk specs:
   for rdid, name in disks:
      disk = CreateDiskSpec(name, rdid, datastoreMgr)
      vm.replicatedDisks.append(disk)

   # Make a simple group spec with the above VM in it
   gspec = Hbr.Replica.GroupSpec()
   gspec.id = groupID
   gspec.rpo = random.randrange(10, 100)
   gspec.vms = [ vm, ]
   gspec.retentionPolicy = AddTierToRetentionPolicy(
                                             None,
                                             random.randrange(gspec.rpo, 24*60),
                                             random.randrange(1, 24))

   return gspec

def CreateHostSpec(addr, auth):
   spec = Hbr.Replica.HostSpec()
   spec.hostId = addr;
   spec.hostAddresses = [addr];
   spec.hostAuth = auth;

   return spec


def PrintDatastores(dsList):
   if (len(dsList) == 0):
      print("Datastore list is empty..")
      return

   print("Printing datastore list...")

   for ds in dsList:
      print("\tDatastore: %s\tAccessible: %s" % (ds.uuid, ds.accessible))
   return

###
### Tests
###


@TestFunc
def TestCreateGroup(count, repManager):
   """Test ReplicationManager CreateGroup method."""

   # Create 'count' random (valid) groups.
   for x in xrange(0, count):
      gspec = CreateRandomizedGroupSpec()
      Log("Created spec: " +str(gspec))
      g = ExpectNoException(repManager.CreateGroup, gspec)
      Log("Got group: " +str(g))
      # check idempotency
      g2 = ExpectNoException(repManager.CreateGroup, gspec)
      if g._moId != g2._moId:
         raise TestFailedExc("Group returned to duplicate CreateGroup call '" +
                             str(g2)+ "' is not equivalent to existing '" +
                             str(g)+ "'.")

   Log("Valid group create tests complete.")


   # Create a valid spec (with at least one valid disk).  To use for
   # causing duplicate-disk errors.
   while True: # Retry until we get at least one valid disk
      validSpec = CreateRandomizedGroupSpec()
      if len(validSpec.vms[0].replicatedDisks) != 0:
         break

   validDiskID = validSpec.vms[0].replicatedDisks[0].diskIdent.id

   invalidGroups = (
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "groupid-same disk twice",
       (("gr1-disk1", "valid-disk-1"),
        ("gr1-disk1", "valid-disk-1")
       )
      ),
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "groupid-same diskid twice",
       (("gr2-disk1", "valid-disk-1"),
        ("gr2-disk1", "valid-disk-2")
       )
      ),
      (Hbr.Replica.Fault.HbrDiskAlreadyExists,
       "groupid-reused diskid",
       (("gr3-disk1", "valid-disk-1"),
        (validDiskID, "valid-disk-2")
       )
      ),
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "group-with-a-too-long-invalid-group-id-that-should-not-be-accepted-ever-no-matter-what-no-matter-how-superb-hbrsrv-ever-becomes",
       (("gr4-disk-1", "valid-disk-1"),
       )
      ),
      (Hbr.Replica.Fault.InvalidHbrDiskSpec,
       "groupid-too long diskid",
       (("disk-with-a-too-long-invalid-disk-id-that-should-not-be-accepted-ever-no-matter-what-no-matter-how-superb-hbrsrv-ever-becomes", "valid-disk-1"),
       )
      ),
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "id-invalid-period.",
       (("gr1-d1", "valid-disk-1"),
        )
       ),
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "id-invalid-bang!",
       (("gr1-d1", "valid-disk-1"),
        )
       ),
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "id-invalid-hash#",
       (("gr1-d1", "valid-disk-1"),
        )
       ),
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "id-invalid-quote'",
       (("gr1-d1", "valid-disk-1"),
        )
       ),
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "id-invalid-dblquote\"",
       (("gr1-d1", "valid-disk-1"),
        )
       ),
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "id-invalid-nl\n",
       (("gr1-d1", "valid-disk-1"),
        )
       ),
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "id-invalid-tab\t",
       (("gr1-d1", "valid-disk-1"),
        )
       ),
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "id-invalid-dollar$",
       (("gr1-d1", "valid-disk-1"),
        )
       ),
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "$#!@_&$**()",
       (("gr1-d1", "valid-disk-1"),
        )
       ),
      (Hbr.Replica.Fault.InvalidGroupSpec,
       "",
       (("gr1-d1", "valid-disk-1"),
        )
       ),
      (Hbr.Replica.Fault.InvalidHbrDiskSpec,
       "valid-gr1",
       (( "gr1-d1-invalid-period.", "valid-disk-1"),
        )
       ),
      (Hbr.Replica.Fault.InvalidHbrDiskSpec,
       "valid-gr1",
       (( "", "valid-disk-1"),
        )
       ),
      (Hbr.Replica.Fault.InvalidHbrDiskSpec,
       "valid-gr1",
       (( "_@$#!$**&&", "valid-disk-1"),
        )
       ),
      )

   # Create the valid group for 'groupid-reused diskid' to conflict with
   g = ExpectNoException(repManager.CreateGroup, validSpec)
   Log("Got 'valid' group (for reused id test): " +str(g))

   for fault, groupID, disks in invalidGroups:
      Log("Creating group with invalid ID(s): " +str(groupID))
      invalGr = CreateInvalidGroupSpec(groupID, disks)
      ExpectException(fault, repManager.CreateGroup, invalGr)

   Log("Try with mismatch between 'group' and 'vm' ids:")
   invalGr = CreateInvalidGroupSpec("group-id-different-from-vm",
                                    (("gr1-d1", "valid-disk-1"), ))
   invalGr.id = "group-id-VERY-DIFFERENT-from-vm"
   ExpectException(Hbr.Replica.Fault.InvalidVirtualMachineSpec,
                   repManager.CreateGroup, invalGr)

   Log("Try with invalid vm datastore configuration:")

   baseSpec = CreateRandomizedGroupSpec()
   for ds in ("invalid/datastore", "/", "/invalid", "invalid/"):
      Log("Setting datastore to: '%s'" % ds)
      baseSpec.vms[0].virtualMachineIdent.datastoreUUID = ds
      ExpectException(Hbr.Replica.Fault.InvalidVirtualMachineSpec,
                      repManager.CreateGroup, baseSpec)

   # Test that we don't accidentally allow duplicate calls when the spec changes
   Log("Negative idempotency tests");

   gspec = CreateRandomizedGroupSpec()
   g = ExpectNoException(repManager.CreateGroup, gspec)
   g2 = ExpectNoException(repManager.CreateGroup, gspec)
   if g._moId != g2._moId:
      raise TestFailedExc("Group returned to duplicate CreateGroup call '" +
                          str(g2)+ "' is not equivalent to existing '" +
                          str(g)+ "'.")

   # Test with completely different spec
   gspec2 = CreateRandomizedGroupSpec()
   gspec2.id = gspec.id
   gspec2.vms[0].virtualMachineIdent.id = gspec.id
   ExpectException(Hbr.Replica.Fault.GroupAlreadyExists,
                   repManager.CreateGroup, gspec2)

   # Test with slightly different specs
   gpsec2 = copy.deepcopy(gspec)
   gspec2.rpo = gspec2.rpo + 1;
   ExpectException(Hbr.Replica.Fault.GroupAlreadyExists,
                   repManager.CreateGroup, gspec2)

   # Test with different VM spec
   gpsec2 = copy.deepcopy(gspec)
   gspec2.vms = [ CreateRandomizedVMSpec(None, vmID=gspec.id) ]
   ExpectException(Hbr.Replica.Fault.GroupAlreadyExists,
                   repManager.CreateGroup, gspec2)

   # Test with different disks
   gpsec2 = copy.deepcopy(gspec)
   gspec2.vms[0].replicatedDisks.append(CreateRandomizedDiskSpec(None))
   ExpectException(Hbr.Replica.Fault.GroupAlreadyExists,
                   repManager.CreateGroup, gspec2)

   Log("All invalid group create tests complete.")


@TestFunc
def TestGetInvalidGroup(repManager):
   """Test ReplicationManager.GetGroup with invalid group."""
   ExpectException(Hbr.Replica.Fault.GroupNotFound,
                   repManager.GetGroup, "invalid-group-id")


@TestFunc
def TestGetValidGroup(repManager):
   """Test ReplicationManager.GetGroup with a valid group."""

   validID = CreateRandomId("valid-group")
   gspec = CreateRandomizedGroupSpec(groupID=validID)

   newGroup = ExpectNoException(repManager.CreateGroup, gspec)
   fetchGroup = ExpectNoException(repManager.GetGroup, validID)

   if fetchGroup._moId != newGroup._moId:
      raise TestFailedExc("New group '" +str(newGroup)+ "' is not "
                          "equivalent to fetched '" +str(fetchGroup)+ "'.")

   Log("Created and looked up '" +str(newGroup)+ "'.")


@TestFunc
def TestGetGroup(repManager):
   """Test ReplicationManager GetGroup method."""

   TestGetInvalidGroup(repManager)
   TestGetValidGroup(repManager)


@TestFunc
def TestGetGroups(repManager):
   # This test needs to run when there are no groups in the server (i.e. before
   # other tests)
   """Test ReplicationManager groups property."""

   # Check that we get no groups initially

   groups = repManager.groups

   if len(groups) != 0:
      raise TestFailedExc("Expected no groups, server reported " +
                          str(groups))

   # Add a group, check that we get it

   group1Id = CreateRandomId("getgroups1")
   group1Spec = CreateRandomizedGroupSpec(groupID=group1Id)
   group1 = ExpectNoException(repManager.CreateGroup, group1Spec);

   groups = repManager.groups

   if (len(groups) != 1) or (group1._moId != groups[0]._moId):
      raise TestFailedExc("Expected 1 group " + str(group1) + " received " +
                          str(groups))

   # Add another group, check that we get both

   group2Id = CreateRandomId("getgroups2")
   group2Spec = CreateRandomizedGroupSpec(groupID=group2Id)
   group2 = ExpectNoException(repManager.CreateGroup, group2Spec);

   groups = repManager.groups

   if len(groups) != 2 or not \
      (((group1._moId == groups[0]._moId) and \
        (group2._moId == groups[1]._moId)) \
       or
       ((group1._moId == groups[1]._moId) and \
        (group2._moId == groups[0]._moId))):
      raise TestFailedExc("Expected 2 groups " + str(group1) + " and " +
                          str(group2) + " but received " + str(groups))

   # Remove both groups, check that again we get no groups

   ExpectNoException(group1.Remove)
   ExpectNoException(group2.Remove)

   groups = repManager.groups

   if len(groups) != 0:
      raise TestFailedExc("Expected no groups, server reported " +
                          str(groups))


@TestFunc
def TestAddGroupErrorCleanup(repManager):
   """Test ReplicationManager cleanup on error in AddGroup"""

   global defaultDsMgr

   gspec1 = CreateRandomizedGroupSpec()
   gspec2 = CreateRandomizedGroupSpec()

   #   Create a bogus disk

   disk = Hbr.Replica.DiskSpec()
   disk.diskIdent = Hbr.Replica.IdentSpec()
   disk.diskIdent.id = CreateRandomId("disk-id")
   disk.diskIdent.datastoreUUID = defaultDsMgr.DatastoreUUID()
   disk.diskIdent.pathname = "bogus/path/baby.vmdk"

   #   Add disk to both groups

   gspec1.vms[0].replicatedDisks.append(disk)
   gspec2.vms[0].replicatedDisks.append(disk)


   Log("Adding group 1 with bogus disk");

   group1 = ExpectNoException(repManager.CreateGroup, gspec1);

   Log("Trying to add group 2 with same bogus disk");

   ExpectException(Hbr.Replica.Fault.HbrDiskAlreadyExists, repManager.CreateGroup, gspec2)

   #   Add it again, shouldn't matter

   ExpectException(Hbr.Replica.Fault.HbrDiskAlreadyExists, repManager.CreateGroup, gspec2)

   Log("Removing group 1");

   ExpectNoException(group1.Remove);

   Log("Adding group 2");

   group2 = ExpectNoException(repManager.CreateGroup, gspec2);

   Log("Removing group 2")

   ExpectNoException(group2.Remove)


@TestFunc
def TestRemoveGroup(repManager):
   """Test Group Remove method"""

   gspec = CreateRandomizedGroupSpec()
   newGroup = ExpectNoException(repManager.CreateGroup, gspec)

   Log("Created valid group " +str(newGroup)+ ".  Will delete it now.")
   ExpectNoException(newGroup.Remove)

   Log("Deleted group " +str(newGroup)+ ".  Will delete it again.")
   ExpectManagedObjectNotFound(newGroup.Remove)

   Log("Re-add group " +str(gspec)+ ".")
   ExpectNoException(repManager.CreateGroup, gspec)


@TestFunc
def TestUnconfigureGroup(repManager):
   """Test Group Unconfigure method"""

   # Create the group
   gspec = CreateRandomizedGroupSpec()
   newGroup = ExpectNoException(repManager.CreateGroup, gspec)

   # Unconfigure the group
   Log("Created valid group " +str(newGroup)+ ".  Will unconfigure it now.")
   ExpectNoException(newGroup.Unconfigure)

   Log("Unconfigured group " +str(newGroup)+ ".  Will unconfigure it again (error).")
   ExpectManagedObjectNotFound(newGroup.Unconfigure)

   Log("Re-add group " +str(gspec)+ ".")
   ExpectNoException(repManager.CreateGroup, gspec)


@TestFunc
def TestRecoverGroup(repManager):
   """Test Group Recover method"""

   # Create the group
   gspec = CreateRandomizedGroupSpec()
   newGroup = ExpectNoException(repManager.CreateGroup, gspec)

   # Unconfigure the group
   Log("Created valid group " +str(newGroup)+ ".  Will unconfigure it now.")
   ExpectNoException(newGroup.Unconfigure)

   # Recover the group (equivalent to createGroup for now)
   Log("Recover unconfigured group " +str(newGroup)+ ".  Will delete it again.")
   ExpectManagedObjectNotFound(newGroup.Unconfigure)

   Log("Re-add group " +str(gspec)+ ".")
   ExpectNoException(repManager.CreateGroup, gspec)


@TestFunc
def TestAddRemoveDisk(repManager):
   """Test ReplicationManager RemoveGroup method"""

   groupID = CreateRandomId("addrm-group-id")

   disk1Spec = CreateRandomizedDiskSpec(datastoreMgr=None)
   disk2Spec = CreateRandomizedDiskSpec(datastoreMgr=None)
   disk3Spec = CreateRandomizedDiskSpec(datastoreMgr=None)

   vmSpec = Hbr.Replica.VirtualMachineSpec()
   vmSpec.virtualMachineIdent = CreateRandomizedVMIdent(datastoreMgr=None,
                                                        vmID=groupID)
   vmSpec.replicatedDisks = [ disk1Spec ]

   gSpec = Hbr.Replica.GroupSpec()
   gSpec.id = groupID
   gSpec.rpo = 13
   gSpec.vms = [ vmSpec ]

   Log("Creating group")

   g = ExpectNoException(repManager.CreateGroup, gSpec)
   vms = g.GetVms()

   ExpectCond(len(vms) == 1, "Group should contain 1 VM")
   vm = vms[0]

   Log("Adding disk 2")

   d2 = ExpectNoException(vm.AddDisk, disk2Spec)
   ExpectException(Hbr.Replica.Fault.HbrDiskAlreadyExists, vm.AddDisk, disk2Spec)
   ExpectCond(not d2.unconfigured, "Disk is unconfigured after add!")

   ExpectException(Hbr.Replica.Fault.HbrDiskNotUnconfigured, vm.RemoveDisk, d2)
   ExpectCond(not d2.unconfigured, "Disk became unconfigured!")

   ExpectNoException(vm.UnconfigureDisk, d2)
   ExpectCond(d2.unconfigured, "Disk is not unconfigured after unconfigure!")

   ExpectNoException(vm.UnconfigureDisk, d2)
   ExpectCond(d2.unconfigured, "Disk became configured!")

   ExpectNoException(vm.RemoveDisk, d2)
   ExpectManagedObjectNotFound(vm.RemoveDisk, d2)

   Log("Removing disk 1")

   d1 = ExpectNoException(vm.GetDisk, disk1Spec.diskIdent.id)
   ExpectCond(not d1.unconfigured, "Disk is already unconfigured!")

   ExpectException(Hbr.Replica.Fault.HbrDiskNotUnconfigured, vm.RemoveDisk, d1)
   ExpectCond(not d1.unconfigured, "Disk became configured!")

   ExpectNoException(vm.UnconfigureDisk, d1)
   ExpectCond(d1.unconfigured, "Disk is not unconfigured after unconfigure!")
   ExpectNoException(vm.RemoveDisk, d1)

   Log("Adding all disks and removing")

   d1 = ExpectNoException(vm.AddDisk, disk1Spec)
   d2 = ExpectNoException(vm.AddDisk, disk2Spec)
   d3 = ExpectNoException(vm.AddDisk, disk3Spec)

   ExpectNoException(vm.UnconfigureDisk, d1)
   ExpectNoException(vm.UnconfigureDisk, d2)
   ExpectNoException(vm.RemoveDisk, d2)
   ExpectNoException(vm.UnconfigureDisk, d3)
   ExpectNoException(vm.RemoveDisk, d1)
   ExpectNoException(vm.RemoveDisk, d3)

   ExpectNoException(g.Remove)


@TestFunc
def TestGroupVMs(gspec, group):

   # Note that 'vms' is a property, not a method
   Log("Test .vms property");
   vms = group.vms
   if len(vms) != 1:
      raise TestFailedExc("Groups should only contain 1 VM!")

   Log("Got vm " +str(vms[0]))

   # GetVirtualMachineIdent
   # GetDisks
   # ChangeConfigLocation


@TestFunc
def TestReplicaGroup(repManager):
   rpo=42
   retentionPolicy = AddTierToRetentionPolicy(None, 60, 4)

   gspec = CreateRandomizedGroupSpec(rpo=rpo, retentionPolicy=retentionPolicy)
   group = ExpectNoException(repManager.CreateGroup, gspec)

   Log("Created group for testing ReplicaGroup API: " +str(group))

   TestGroupVMs(gspec, group)

   Log("Test GetRpo");
   returnRpo = group.GetRpo()
   if returnRpo != rpo:
      raise TestFailedExc("RPO should be " + str(rpo) + ", not " + str(returnRpo));

   Log("Test UpdateRpo (valid RPO values)");
   for nRpo in [ 0, 1, 11, 13, 99, 100, 1000, 1440 ]:
      ExpectNoException(group.UpdateRpo, nRpo)
      returnRpo = group.GetRpo()
      if returnRpo != nRpo:
         raise TestFailedExc("RPO should be " + str(nRpo) + ", not " + str(returnRpo));

   Log("Test UpdateRpo (invalid RPO values)");
   invalRpoFault = Vmodl.Fault.InvalidArgument
   for nRpo in [ -1000, -1, 1441, 100*1000*1000 ]:
      ExpectException(invalRpoFault, group.UpdateRpo, nRpo)

   Log("Test GetRetentionPolicy");
   returnPolicy = group.GetRetentionPolicy()
   if RetentionPolicyToString(returnPolicy) != RetentionPolicyToString(retentionPolicy):
      raise TestFailedExc("Retention policy should be " +
               RetentionPolicyToString(retentionPolicy) + ", not " +
               RetentionPolicyToString(returnPolicy));

   Log("Test UpdateRetentionPolicy (valid retention policy values)");
   testPolicy = AddTierToRetentionPolicy(None, 0, 8)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 5, 14)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 15, 3)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 45, 16)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 120, 8)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 360, 10)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 1140, 2)
   totalSlots = 0
   retentionPolicy = None
   for tier in testPolicy.tiers:
      if totalSlots + tier.GetNumSlots() > 24:
         totalSlots = 0
         retentionPolicy = None
      retentionPolicy = AddTierToRetentionPolicy(retentionPolicy,
                                                 tier.GetGranularityMinutes(),
                                                 tier.GetNumSlots())
      totalSlots += tier.GetNumSlots()
      ExpectNoException(group.UpdateRetentionPolicy, retentionPolicy)
      returnPolicy = group.GetRetentionPolicy()
      if RetentionPolicyToString(returnPolicy) != RetentionPolicyToString(retentionPolicy):
         raise TestFailedExc("Retention policy should be " +
                  RetentionPolicyToString(retentionPolicy) + ", not " +
                  RetentionPolicyToString(returnPolicy));

   Log("Test UpdateRetentionPolicy (invalid retention policy values)");
   testPolicy = AddTierToRetentionPolicy(None, -1, 8)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 0, -1)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 15, 0)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 45, 36)
   invalidPolicyFault = Vmodl.Fault.InvalidArgument
   for tier in testPolicy.tiers:
      retentionPolicy = AddTierToRetentionPolicy(None,
                                                 tier.GetGranularityMinutes(),
                                                 tier.GetNumSlots())
      ExpectException(invalidPolicyFault, group.UpdateRetentionPolicy, retentionPolicy)

   # Test repeating the same granularity mins
   testPolicy = AddTierToRetentionPolicy(None, 5, 2)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 10, 6)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 10, 12)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 20, 1)
   ExpectException(invalidPolicyFault, group.UpdateRetentionPolicy, testPolicy)

   # Test total number of slots greater than default max of 24
   testPolicy = AddTierToRetentionPolicy(None, 3, 9)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 19, 8)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 43, 6)
   testPolicy = AddTierToRetentionPolicy(testPolicy, 111, 7)
   ExpectException(invalidPolicyFault, group.UpdateRetentionPolicy, testPolicy)

   Log("Test GetState");
   st = group.GetState()
   if st != "passive":
      raise TestFailedExc("State should be 'passive'")
   else:
      Log("Group is 'passive'")

   Log("Test GetId");
   ExpectNoException(group.GetId)

   Log("Test GetCurrentRpoViolation");
   rpoViolation = group.GetCurrentRpoViolation()
   if (rpoViolation != -1):
      raise TestFailedExc("Rpo violation should initially be -1, not " + str(rpoViolation));

   # group.Remove tested elsewhere

   # Can't test CommitToImage without an image ...
   #Log("Test CommitToImage");
   #ExpectNotImplemented(group.CommitToImage, None)

   # Note that .Instances is a property, not a method
   Log("Test .instances property");
   insts = group.instances
   if len(insts) > 0:
      raise TestFailedExc("Groups should contain 0 instances!")
   else:
      Log("No instances.")

   # Note: that .latestInstance is a property, not a method
   inst = group.latestInstance
   Log("Got .latestInstance " +str(inst))
   if inst:
      raise TestFailedExc("Group should not have a 'latest' instance!")
   else:
      Log("No latest instance.")



@TestFunc
def TestHosts(repManager,
              datastoreConf):

   storageManager = repManager.GetStorageManager()

   # unpack the legitimate datastore configuration
   (host, user, password) = datastoreConf

   randHost = CreateRandomId("host-")
   randUser1 = CreateRandomId("user-")
   randUser2 = CreateRandomId("user1-")
   randPass = CreateRandomId("pass-")

   Log("Test EnableHost")
   # Test adding a new host
   hspec = CreateHostSpec(randHost, randUser1 + ":" + randPass)
   newHost1 = ExpectNoException(storageManager.EnableHost, hspec)
   print("Added host %s" % newHost1.GetId)

   # Test modifying the user of existing host
   hspec = CreateHostSpec(randHost, randUser2 + ":" + randPass)
   newHost2 = ExpectNoException(storageManager.EnableHost, hspec)

   # Test modifying password of existing host
   hspec = CreateHostSpec(randHost, randUser2 + ":")
   newHost2 = ExpectNoException(storageManager.EnableHost, hspec)

   # Since EnableHost is idempotent, get a reference to existing valid host
   hspec = CreateHostSpec(host, user + ":" + password)
   validHost = ExpectNoException(storageManager.EnableHost, hspec)

   # Test removing the host
   Log("Test removing hosts...")
   ExpectNoException(newHost1.Remove)
   ExpectNoException(validHost.Remove)

   # There should be no valid hosts existing and hence all configured
   # datastores should be marked inaccessible.
   dsList = storageManager.GetExpectedDatastores()
   for ds in dsList:
      if (ds.accessible):
         PrintDatastores(dsList)
         raise TestFailedExc("Removing all hosts should mark all datastores inaccessible")

   Log("Test EnableHost with null configurations")

   # Try with ..
   # .. invalid host name
   ExpectException(Hbr.Replica.Fault.InvalidHostSpec,
                   storageManager.EnableHost,
                   CreateHostSpec("", randUser1+":"+randPass))
   # .. invalid user/pass
   ExpectException(Hbr.Replica.Fault.InvalidHostSpec,
                   storageManager.EnableHost,
                   CreateHostSpec("valid", ":"))

   ExpectException(Hbr.Replica.Fault.InvalidHostSpec,
                   storageManager.EnableHost,
                   CreateHostSpec("valid", "@"))
   # .. invalid user
   ExpectException(Hbr.Replica.Fault.InvalidHostSpec,
                   storageManager.EnableHost,
                   CreateHostSpec("valid", ":"+randPass))

   # Add the valid host with an invalid password, expect failures:
   validHost = ExpectNoException(storageManager.EnableHost,
                                 CreateHostSpec(host, user + ":" + password + "BORKED"))

   if validHost.accessible:
      raise TestFailedExc("Valid host, with bad password, should not be accessible.");

   # Fixup the host (later tests expect it to be present in the server)
   validHost = ExpectNoException(storageManager.EnableHost,
                                 CreateHostSpec(host, user + ":" + password))
   if not validHost.accessible:
      raise TestFailedExc("Valid host should be accessible.");

   return


@TestFunc
def TestDatastores(repManager,
                   datastoreConf,
                   dsMgrList):

   storageManager = repManager.GetStorageManager()

   Log("Test configured datastores")
   # Create a group on each datastore
   for datastoreMgr in dsMgrList:
      gspec = CreateRandomizedGroupSpec(datastoreMgr=datastoreMgr)
      newGroup = repManager.CreateGroup(gspec)

   dsList = storageManager.GetExpectedDatastores()

   # There should be at least one datastore for each CreateGroup above
   if len(dsList) != len(dsMgrList):
      Log("Expected datastores present...")
      PrintDatastores(dsList)
      Log("Test provided datastores...")
      PrintDatastores(dsMgrList)
      raise TestFailedExc("Expected " + str(len(dsMgrList)) + " datastores. " +
                          "Found " + str(len(dsList)) + ".")
   PrintDatastores(dsList)

   numDs = len(dsList)

   # Test datastore removal (triggered by removal of all groups)
   Log("Test datastore removal...")
   for group in repManager.groups:
      group.Remove()
      dsList = storageManager.GetExpectedDatastores()
      newNumDs = len(dsList)
      if numDs != newNumDs:
         print("Remaining datastores...")
         PrintDatastores(dsList)
      newNumDs = numDs

   dsList = storageManager.GetExpectedDatastores()    # Should have no datastores...
   numDs = len(dsList)

   if numDs != 0:
      Log("Groups that still exist")
      for group in repManager.groups:
         print(group)
      Log("Datastores that weren't removed...")
      PrintDatastores(dsList)
      raise TestFailedExc("Expected zero datastores. Found " + str(numDs) + ".")

   return


@TestFunc
def TestReplicationManager(repManager, datastoreConf, dsMgrList):
   """Test the currently implemented interfaces of the
   hbr.replica.ReplicationManager."""

   # Test Host API interfaces
   TestHosts(repManager, datastoreConf)

   # Basic ReplicationManager API interfaces:
   TestGetGroups(repManager)
   #TestCreateGroup(100, repManager)
   TestCreateGroup(13, repManager)
   TestGetGroup(repManager)
   TestRemoveGroup(repManager)
   TestAddGroupErrorCleanup(repManager)
   TestUnconfigureGroup(repManager)
   TestRecoverGroup(repManager)

   TestAddRemoveDisk(repManager)

   # ReplicaGroup API:
   TestReplicaGroup(repManager)

   # Datastore API (removes all groups in the database!)
   TestDatastores(repManager, datastoreConf, dsMgrList)

   return


# Test certificate for connecting to the server (just a
# self-signed certificate with the thumbprint below and
# the corresponding private key.
#
# Used to test login-by-SSL thumbprint functionality.

testCertificate = '''
-----BEGIN CERTIFICATE-----
MIIEHjCCAwagAwIBAgIIZ1NXRlNVc3kwDQYJKoZIhvcNAQEFBQAwPDE6MDgGA1UE
ChMxVk13YXJlIEhvc3QtYmFzZWQgcmVwbGljYXRpb24gdGVzdGluZyBTZWxmLVNp
Z25lZDAeFw0xMDAzMjEwMjI4MTVaFw0yMTA5MTkwMjI4MTVaMIIBJTELMAkGA1UE
BhMCVVMxEzARBgNVBAgTCkNhbGlmb3JuaWExEjAQBgNVBAcTCVBhbG8gQWx0bzEU
MBIGA1UEChMLVk13YXJlLCBJbmMxPDA6BgNVBAsTM1ZNd2FyZSBIb3N0LWJhc2Vk
IHJlcGxpY2F0aW9uIHNlcnZlci10ZXN0aW5nIGNsaWVudDEqMCgGCSqGSIb3DQEJ
ARYbc3NsLWNlcnRpZmljYXRlc0B2bXdhcmUuY29tMTswOQYDVQQDEzJWTXdhcmUg
SG9zdC1iYXNlZCBSZXBsaWNhdGlvbiBzZXJ2ZXItdGVzdGluZyBjbGllbjEwMC4G
CSqGSIb3DQEJAhMhMTI2OTEzODQ5NSw1NjRkNzc2MTcyNjUyMDQ5NmU2MzJlMIIB
IjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAokBMmaIam/yvJucCB9J7IdWn
LKh3qAaZrBqXu1li9NC8tfauN5YIeQDjsbkCE2lo3uIwvZAaNYYUr/Hx5xnwrk+g
/t3GM7NJJshwbfOJUih1ACpokyI5xwnQPWgtSef/rM5K2GIJPo6fsDjcLrGHhiNC
KS1L2SNRd2y34m9AKjJ2JkNA02FgwWSCoWpKzVeicpR6p2zipJAWo+XgzAOs6xhe
8wo10XtO3gBBdoz0+Vfx1SDWtUVpIHdijI7p+SdNtWGPYvdfCwprD2sD4Brwh/qC
LDLYnuNs4yxuu3wYoVHf77DoCAkteAzKt/hEfiEgNKplMewnt8Jt3RjCljvbIQID
AQABozkwNzAJBgNVHRMEAjAAMAsGA1UdDwQEAwIEsDAdBgNVHSUEFjAUBggrBgEF
BQcDAQYIKwYBBQUHAwIwDQYJKoZIhvcNAQEFBQADggEBAGqprZtEbphM7lvflOab
2kTQd5WslOnuq8snMdQpo0EwGPHTlxwEYRX7AIgtz7b7o4mJjeifyXdRxISoMRY9
/g0uSZnrdgTXR0UtZ5RhUXpYcZc36dwZ09b94HvZQc655pD55hJFjN2jP3F4yVsb
Qzfa3HonJjINEWVnHarR/UrpbzuN5OZO+Chs7xqIvCr30y5LfKBYKKKoJrsxWGl5
6wTLqsUzlCdnKtvOb5dilWSxfmcf6YjkzoE4SK4koiRLoVw8ktPptNESTAA87TR9
dP1uhyZRo9cQImrAu1iOCezNQNWBwpm6/rjpbKcJsfAEu2VQlp6zJF4on8laLGSd
fx0=
-----END CERTIFICATE-----
'''

testCertificateThumbprint = \
   '02:C7:95:22:D4:5D:D3:37:FD:51:A1:DE:A4:F0:D4:AE:DB:0E:43:B7'

testCertificateKey = '''
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAokBMmaIam/yvJucCB9J7IdWnLKh3qAaZrBqXu1li9NC8tfau
N5YIeQDjsbkCE2lo3uIwvZAaNYYUr/Hx5xnwrk+g/t3GM7NJJshwbfOJUih1ACpo
kyI5xwnQPWgtSef/rM5K2GIJPo6fsDjcLrGHhiNCKS1L2SNRd2y34m9AKjJ2JkNA
02FgwWSCoWpKzVeicpR6p2zipJAWo+XgzAOs6xhe8wo10XtO3gBBdoz0+Vfx1SDW
tUVpIHdijI7p+SdNtWGPYvdfCwprD2sD4Brwh/qCLDLYnuNs4yxuu3wYoVHf77Do
CAkteAzKt/hEfiEgNKplMewnt8Jt3RjCljvbIQIDAQABAoIBABfUzet67eGfebKD
F79CYSeVFBrxG7IoVgX7WfIArRI8Xptzgh9UACaVxNvjyrRDNU4XdwVA1zipWvyE
0v0YyEsyEvmcZXJOkR4LLshXjwHsQ1Mk53tE+auMe3Opi41hcCJXopKpw6XWmQnv
MBgDp15Ca4NUzeE02NBrvY6avJf12ZeTDzmq3zR+H2fKhAL5DbQmd1aeidQ6UI+M
JGp5AFjpjvhnlE8CZbNMr0iJztIkwJ4hE4eUIU3MH7W+IrNSRax9S7FiJKpwV7m/
TcY3K03xyNE3AAlWDDtSRcJlpjz2VoE1akF3yOD3w8UE8ll5sCV7NazF8212UqqJ
/ai/G4ECgYEAz3lPtvTmqMnv35jItLyAMWsgHkJ1uK3NbdSBFf84UmjZnFcsCRug
2l8X3Jv0jhPR2PVqhE0/lGmBcHuOgqDtK3fTszhrF/Q2w3OhjZ9ZNGHIKLkGszsD
Cq1hEjH+JiXZlS/wuldbyumDTOGdiWxkwFsMRIcCfmvcuA/QgbmvzekCgYEAyDM8
pwz21tVTcw8s8oW5KKjhJYcCiNVM7jnOiJAe8f5/cQR6ABGjprbn5lZWdtrKenPn
2aY1yL/Ajn/nw+iOkmV5N712CxOAkZX2QpDVsZaOgZTK/Tkpy9xeqsK9R1srLoR/
/kZnbo67k4SHvuM/ViN2JtaJs9fziTTTBNgqSHkCgYAlKaqgr+9dDobb+0cAML+Z
moGvSeJCSUeBw823ffa9tDA+c9Lccsl2NBBXIMxGYsB050jEF/4qfFeGKWuWdHLn
FVijQpjUOpdQnTaz4nYdDuLGgJX1pr1dvT6k/rVyadc2hNbO2fUEPJ2bONJ6GiNV
3TkuUSyeLn3jrll/0x3teQKBgBHe0PkwZRBENpC8uAxl92Mzv/UzmfxQ3e8d5du2
0axURVf3SFSdPnhxNz4OUuWFHjHUCswY1BA5XZzauft41NEokatyFAllEkLsmfDT
MOALSmkyuPPlmF+EKkcf3vlxn+clGK+/5RevUfsXB274pfywaamJ2Pzet/R1bKiw
CwYxAoGBAIS+xJ+emUpG82vSEAOv62V8BpOWH43BTx2KglZEshsdaQSOJvhO0u3R
b2MSrEhpeKAVpcgoG2stQBtQG4tqvZvF/pWVjRol2vvzJP4lBNbul8gFv70VBU7b
zJd5bHBuXckscdFBy/EA88d9YrySm26gseRFFvnFSgYz1NVfHKgp
-----END RSA PRIVATE KEY-----
'''

guestInfoScript = "/usr/bin/hbrsrv-guestinfo.sh"
hmsThumbprintKey = "guestinfo.hbr.hms-thumbprint"
srvThumbprintKey = "guestinfo.hbr.hbrsrv-thumbprint"
srvRevokedKey = "guestinfo.hbr.hbrsrv-certificate-revoked"


@TestFunc
def TestSessionManager(repMgr,
                       sessionMgr,
                       localuser='root',
                       localpasswd='vmware'):
   """
   Test the interfaces of hbr.replica.SessionManager.  Assumes the session
   is not yet authenticated.
   """

   TestSessionMethodsWhileNotLoggedIn(repMgr, sessionMgr)

   Log("Trying simple valid login/logoff.")
   sessionMgr.Login(localuser, localpasswd)
   sessionMgr.Logoff()

   Log("Trying login and double-login")
   sessionMgr.Login(localuser, localpasswd)
   # double-login is a failure
   ExpectException(Hbr.Replica.Fault.AlreadyLoggedIn,
                   sessionMgr.Login, localuser, localpasswd)

   Log("Logging off")
   sessionMgr.Logoff()

   TestSessionMethodsWhileNotLoggedIn(repMgr, sessionMgr)

   #
   # We don't validate user/pass anymore so there's no need
   # to test for bad user/pass combos here.
   #

   Log("Trying bad thumbprint login")

   RunCommand([guestInfoScript, "set", hmsThumbprintKey, "bad-login-test-thumbprint"])

   sessionMgr.ReadGuestInfoKeys();

   ExpectException(Hbr.Replica.Fault.InvalidLogin, sessionMgr.LoginBySSLThumbprint)

   Log("Trying good thumbprint login")

   RunCommand([guestInfoScript, "set", hmsThumbprintKey,
               testCertificateThumbprint])

   sessionMgr.ReadGuestInfoKeys()

   sessionMgr.LoginBySSLThumbprint()

   Log("Trying double thumbprint login")
   ExpectException(Hbr.Replica.Fault.AlreadyLoggedIn, sessionMgr.LoginBySSLThumbprint)

   Log("Double log off")
   sessionMgr.Logoff()
   sessionMgr.Logoff() # should be ok

   Log("Forcing the server to generate new certficate")
   sessionMgr.LoginBySSLThumbprint()

   cmd = "%s get %s" % (guestInfoScript, srvThumbprintKey);
   (status, oldThumbprint) = commands.getstatusoutput(cmd);

   if status != 0:
      raise TestFailedExc("Error getting server thumbprint, script returned: " +
                          str(rc))

   if not re.match("[0-9A-F][0-9A-F](:[0-9A-F][0-9A-F])+$", oldThumbprint):
      raise TestFailedExc("Guestinfo contains invalid hbrsrv thumbprint: " +
                          oldThumbprint);

   # BEWARE: this changes the *REAL* server's SSL key (we're generally
   # running a secondary server on the side), but this stuff is shared.
   # The test-hbrsrv.sh wrapper script saves/restores the original SSL
   # key.
   RunCommand([guestInfoScript, "set", srvRevokedKey, "1"])

   RunCommand([guestInfoScript, "set", hmsThumbprintKey, "post-login-test-thumbprint"])

   # Kick hbrsrv, disconnects all VMODL connections
   Log("Restarting VMODL service")
   sessionMgr.RestartVmodlServer()

   sessionMgr = None  # The session manager moref (and soap stub) are useless now

   (status, newThumbprint) = commands.getstatusoutput(cmd);

   if status != 0:
      raise TestFailedExc("Error getting server thumbprint, script returned: " +
                          str(rc))

   if not re.match("[0-9A-F][0-9A-F](:[0-9A-F][0-9A-F])+$", oldThumbprint):
      raise TestFailedExc("Guestinfo contains invalid hbrsrv thumbprint: " +
                          oldThumbprint);

   if oldThumbprint == newThumbprint:
      raise TestFailedExc("Thumbprint didn't change!")

   Log("Done with SessionManager tests")

   return


@TestFunc
def TestSessionMethodsWhileNotLoggedIn(repMgr, sessionMgr):
   """Test some APIs behavior when not logged in."""

   # Valid SSL key may be left in database from startup after valid key
   # was found in guest-info
   sessionMgr.ReadGuestInfoKeys();

   # GetReplicationManager requires a valid login
   Log("Trying methods that require a login (expecting SecurityError exceptions)")
   ExpectException(Vmodl.Fault.SecurityError,
                   sessionMgr.RestartVmodlServer,)
   ExpectException(Vmodl.Fault.SecurityError,
                   repMgr.GetGroup, "invalid-group-id")
   ExpectException(Vmodl.Fault.SecurityError,
                   repMgr.GetServerStats,)

   # Test a couple methods that are allowed even if not logged in:
   Log("Trying always-allowed methods without login")
   sessionMgr.ReadGuestInfoKeys();
   repMgr.GetStorageManager();
   repMgr.GetServerDetails();
   repMgr.GetPropertyCollector();

   Log("Trying redundant logoff")
   sessionMgr.Logoff() # redundant logoff should be okay


@TestFunc
def TestSupportBundles(sMgr):
   """Test the support bundle APIs"""

   Log("Simple negative tests of supportBundleChunk")
   # XXX what's up with BadStatusLine here?
   ExpectException(Vmodl.Fault.InvalidArgument,
                   sMgr.SupportBundleChunk, "", 0, 0)
   ExpectException(Vmodl.Fault.InvalidArgument,
                   sMgr.SupportBundleChunk, "", 0, 0)
   ExpectException(Vmodl.Fault.InvalidArgument,
                   sMgr.SupportBundleChunk, "", 10*100, 0)
   ExpectException(Vmodl.Fault.InvalidArgument,
                   sMgr.SupportBundleChunk, "", 0, 1)
   ExpectException(Vmodl.Fault.InvalidArgument,
                   sMgr.SupportBundleChunk, "../etc/passwd", 0, 0)
   ExpectException(Vmodl.Fault.InvalidArgument,
                   sMgr.SupportBundleChunk, "foo/../etc/passwd", 0, 0)
   ExpectException(Vmodl.Fault.InvalidArgument,
                   sMgr.SupportBundleChunk, "doesnotexist.tgz", 0, 0)

   Log("Generate a bundle.")
   sbi = sMgr.GenerateSupportBundle()
   chunk = sMgr.SupportBundleChunk(sbi.key, 0, 10)
   if len(chunk) != 10:
      raise TestFailedExc("Chunk should have at least 10 bytes");

   sMgr.SupportBundleChunk(sbi.key, 0, 10)
   if len(chunk) != 10:
      raise TestFailedExc("(Idempotent) chunk should have at least 10 bytes");

   sMgr.SupportBundleChunk(sbi.key, 0, 10*1000*1000)
   ExpectException(Vmodl.Fault.InvalidArgument,
                   sMgr.SupportBundleChunk,
                   sbi.key, 1000*1000*1000*100, 10)

   Log("Generate 5 bundles to force recycling.")
   sbiFirst = sMgr.GenerateSupportBundle()
   sbi = sMgr.GenerateSupportBundle()
   sbi = sMgr.GenerateSupportBundle()
   sbi = sMgr.GenerateSupportBundle()
   sbi = sMgr.GenerateSupportBundle()

   Log("Ensure old bundle keys expire.")
   ExpectException(Vmodl.Fault.InvalidArgument,
                   sMgr.SupportBundleChunk,
                   sbiFirst.key, 0, 10)

   return


@TestFunc
def TestServerManager(sMgr):
   """Test the hbr.replica.ServerManager API."""

   TestSupportBundles(sMgr)

   # Tested elsewhere
   # sMgr.shutdown()

   Log("Testing logModules")
   for m in sMgr.GetLogModules():
      print(m)



#
# main
#
def main():
   # Only the datastore manager for the default
   # datastore is global
   global defaultDsMgr
   global testdir

   supportedArgs = [
      (["h:", "hbrsrv="], "localhost", "hbrsrv host name", "hbrsrv"),
      (["p:", "port="], 8123, "VMODL port", "port"),
      (["hostd="], 'root:@localhost', "Hostd instance", "hostd"),
      (["datastore="], 'storage1', "datastore to use", "datastore"),
      (["testdir="], 'hbrServer-test', "test directory", "testdir"),
      (["auth="], 'root:vmware', "Local user:password", "auth"),
      ]

   supportedToggles = [
      (["usage", "help"], False, "Show usage information", "usage"),
      ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage"):
      args.Usage()
      return 0

   hbrsrv_host = args.GetKeyValue("hbrsrv")
   hbrsrv_port = int(args.GetKeyValue("port"))
   datastores = args.GetKeyValue('datastore')
   hostd = args.GetKeyValue('hostd')
   testdir = args.GetKeyValue('testdir')
   (localuser, localpasswd) = args.GetKeyValue('auth').split(":")

   # Connect to hostd to create directories and disks:
   try:
      (host, user, password) = pyHbr.disks.ParseHostUserPass(hostd)
      datastoreList = datastores.split(",")
      defaultDsMgr = pyHbr.disks.RemoteStorage(host, user, password, datastoreList[0])
      dsMgrList = []
      for datastore in datastoreList:
         dsMgrList.append(pyHbr.disks.RemoteStorage(host, user, password, datastore))
         Log("Connected to datastore: %s" % str([host, user, password, datastore]))
   except:
      Log("Failing on exception during hostd connection")
      traceback.print_exc(file=sys.stdout)
      status = "FAIL"
      return 1;

   # Create a test directories on the datastores:
   for datastoreMgr in dsMgrList:
      atexit.register(datastoreMgr.CleanupDirectory, testdir)
      datastoreMgr.MakeDirectory(testdir)

   # Add a pause before cleaning up directories in case hbr server is also cleaning something up
   atexit.register(time.sleep, 2)

   Log("Created test directories on datastores.")


   status = "INCOMPLETE"
   try:
      # Key may be left in guest-info from a previous run
      RunCommand([guestInfoScript, "set", hmsThumbprintKey, "initial-invalid"])

      Log("Create SSL key/cert to use as client-side SSL thumbprint.")
      key_file = tempfile.gettempdir() + CreateRandomId("/key");

      f = open(key_file, 'w')
      f.write(testCertificateKey);
      f.close();
      atexit.register(os.unlink, key_file)

      cert_file = tempfile.gettempdir() + CreateRandomId("/cert");
      f = open(cert_file, 'w')
      f.write(testCertificate);
      f.close();
      atexit.register(os.unlink, cert_file)

      hbrCnx = pyHbr.servercnx.EstablishSoapCnx(host=hbrsrv_host,
                                                port=hbrsrv_port,
                                                key_file = key_file,
                                                cert_file = cert_file)

      Log("Connected to hbrsrv: %s:%d: %s" % (hbrsrv_host, hbrsrv_port, str(hbrCnx)))

      repManager = pyHbr.servercnx.HbrReplicationManager(hbrCnx)
      sesManager = pyHbr.servercnx.HbrSessionManager(hbrCnx)

      # Test session manager before authenticating, as this has the API
      # for auth/auth.  Normal APIs are tested below
      TestSessionManager(repManager, sesManager, localuser, localpasswd)

      # re-establish connection and test the rest of the APIs
      # (TestSessionManager resets the VMODL server, severing the old
      # hbrCnx)
      hbrCnx = pyHbr.servercnx.EstablishSoapCnx(host=hbrsrv_host,
                                                port=hbrsrv_port,
                                                key_file = key_file,
                                                cert_file = cert_file)

      repManager = pyHbr.servercnx.HbrReplicationManager(hbrCnx)
      sesManager = pyHbr.servercnx.HbrSessionManager(hbrCnx)

      pyHbr.servercnx.Authenticate(sesManager, localuser, localpasswd)

      TestReplicationManager(repManager, (host, user, password), dsMgrList)

      serverManager = pyHbr.servercnx.HbrServerManager(hbrCnx)
      TestServerManager(serverManager)

      pyHbr.servercnx.ClearAuthentication(sesManager)

      status = "PASS"
   except:
      Log("Failing on unhandled exception: ")
      traceback.print_exc(file=sys.stdout) # to stdout to avoid interleaving
      status = "FAIL"

   Log("TEST RUN COMPLETE: " + status)
   if status != "PASS":
      return 1
   else:
      return 0

# Start program
if __name__ == "__main__":
   rc = main()
   sys.exit(rc)
