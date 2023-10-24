#!/usr/bin/env python

__doc__ = """
@file case_2_Disks.py --
Copyright 2007-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This test suite verifies VM disk operations.
"""

__author__ = "VMware, Inc"

import os
import unittest
import testoob
from pyVim.task import WaitForTask
from pyVim import integtest
from pyVim import vm
from pyVim import invt
from pyVim import vmconfig
from pyVmomi import Vim

class TestDiskOps(integtest.FixtureCreateDummyVM):
    """
    This unit tests disk operations.
    """

    def test1_IncreaseDiskSize(self):
        """
        Increase disk size.
        """
        devices = vmconfig.CheckDevice(self._vm.GetConfig(),
                                       Vim.Vm.Device.VirtualDisk)
        disk_count = len(devices)
        self.failIf(disk_count < 1,
                    "Expected at least one disk. Found %s disks." % disk_count)
        disk = devices[0]
        cspec = Vim.Vm.ConfigSpec()
        newCapacity = disk.GetCapacityInKB() + 8192
        self.failIfRaises("disk.SetCapacityInKB should not raise.",
                          disk.SetCapacityInKB, newCapacity)
        self.failIfRaises("vmconfig.AddDeviceToSpec should not raise.",
                          vmconfig.AddDeviceToSpec,
                          cspec,
                          disk,
                          Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
        self.failIfRaises("Reconfiguring the VM should not raise.",
                          self._vm.Reconfigure, cspec)

        devices = vmconfig.CheckDevice(self._vm.GetConfig(), Vim.Vm.Device.VirtualDisk,
                                       {"capacityInKB": newCapacity})
        new_disk_count = len(devices)
        self.failIf(new_disk_count != disk_count,
                    "Disk count expected to remain the same: %s, it is: %s." % \
                    (disk_count, new_disk_count))

    def test2_DecreaseDiskSize(self):
        """
        Decrease disk size.
        """
        devices = vmconfig.CheckDevice(self._vm.GetConfig(),
                                       Vim.Vm.Device.VirtualDisk)
        disk_count = len(devices)
        self.failIf(disk_count < 1,
                    "Expected at least one, got %s disks." % disk_count)
        disk = devices[0]
        cspec = Vim.Vm.ConfigSpec()
        newCapacity = disk.GetCapacityInKB() - 4096
        self.failIfRaises("disk.SetCapacityInKB should not raise.",
                          disk.SetCapacityInKB, newCapacity)
        self.failIfRaises("vmconfig.AddDeviceToSpec should not raise.",
                          vmconfig.AddDeviceToSpec,
                          cspec,
                          disk,
                          Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
        self.failUnlessRaises("Decreasing disk capacity is expected to raise.",
                              Exception, self._vm.Reconfigure, cspec)

    def test3_ChangeDiskUuid(self):
        pass
# test is broken
#        """
#        Change disk uuid.
#        """
#        devices = vmconfig.CheckDevice(self._vm.GetConfig(),
#                                       Vim.Vm.Device.VirtualDisk)
#        disk_count = len(devices)
#        self.failIf(disk_count < 1,
#                    "Expected at least one, got %s disks." % disk_count)
#        disk = devices[0]
#        cspec = Vim.Vm.ConfigSpec()
#
#        backing = disk.GetBacking()
#        uuid = "6000C29f-c2a6-5c04-3bab-aa781ddeff37"
#        backing.SetUuid(uuid)
#        disk.SetBacking(backing)
#        self.failIfRaises("vmconfig.AddDeviceToSpec should not raise.",
#                          vmconfig.AddDeviceToSpec,
#                          cspec,
#                          disk,
#                          Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
#        self.failIfRaises("self._vm.Reconfigure should not raise.",
#                          self._vm.Reconfigure, cspec)
#
#        devices = vmconfig.CheckDevice(self._vm.GetConfig(),
#                                       Vim.Vm.Device.VirtualDisk,
#                                       {"backing.uuid": uuid})
#        print devices
#        self.failIf(len(devices) != 1, 
#                    "Expected to have one disk with uuid: %s, got: %s." % \
#                        (uuid, len(devices)))

