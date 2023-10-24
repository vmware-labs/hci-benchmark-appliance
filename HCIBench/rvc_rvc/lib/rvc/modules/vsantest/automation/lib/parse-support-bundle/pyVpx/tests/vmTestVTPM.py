##############################################################
# Copyright (c) 2016-2017, 2021 VMware, Inc.  All rights reserved.
# -- VMware Confidential
##############################################################

#!/usr/bin/python

import sys
import time
import getopt
from pyVmomi import vim, vmodl, VmomiSupport
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask
from pyVim import vm
from pyVim import vmconfig
import vimcrypto
from pyVim import arguments
from pyVim import host
from pyVim.helpers import Log
import atexit

TPM_DEV_KEY = 11000

def CreateVTPM(key):
    tpm = vim.vm.device.VirtualTPM()
    tpm.key = key
    return tpm

def CreateVD(key):
    vd = vim.vm.device.VirtualDevice()
    vd.key = key
    return vd

def AddVTPM(cspec, key=None):
    if key is None:
        key = vmconfig.GetFreeKey(cspec)
    tpm = CreateVTPM(key)
    vmconfig.AddDeviceToSpec(cspec, tpm,
                             vim.vm.device.VirtualDeviceSpec.Operation.add)

def CheckTPMNotPresent(vm1):
    """
    Confirm that TPM is not present in a VM.
    """
    tpms = vmconfig.CheckDevice(vm1.config, vim.vm.device.VirtualTPM)
    if len(tpms) != 0:
        raise Exception("TPM found in a VM: " + str(tpms))

def CheckTPMPresent(vm1):
    """
    Validate TPM presence.
    """
    Log("Checking TPM is present...")
    tpms = vmconfig.CheckDevice(vm1.config, vim.vm.device.VirtualTPM)
    if len(tpms) != 1:
        raise Exception("Invalid TPM configuration: " + str(tpms))
    tpm = tpms[0]
    if tpm.key != TPM_DEV_KEY:
        raise Exception("TPM device has unexpected key: " + tpm.key)
    csrs = tpm.endorsementKeyCertificateSigningRequest
    if len(csrs) == 0:
        raise Exception("TPM device does not have any CSRs")
    return tpm

def TestAdd2ndTPMKey(vm1, key):
    """
    Test add 2nd vTPM
    """
    Log("Adding 2nd vTPM using key=%s" % key)
    cspec = vim.vm.ConfigSpec()
    AddVTPM(cspec, key)
    try:
        vm.Reconfigure(vm1, cspec)
        raise Exception("Addition of 2nd vTPM did not fail with %s" % cspec)
    except vim.fault.TooManyDevices as e:
        pass
    CheckTPMPresent(vm1)

def TestAdd2ndTPM(vm1):
    """
    Test add 2nd vTPM
    """
    TestAdd2ndTPMKey(vm1, None)
    TestAdd2ndTPMKey(vm1, 100)
    TestAdd2ndTPMKey(vm1, TPM_DEV_KEY)
    TestAdd2ndTPMKey(vm1, -1)
    TestAdd2ndTPMKey(vm1, 1999999999)
    TestAdd2ndTPMKey(vm1, -1999999999)

def TestVTPMHotAdd(vm1):
    Log("Trying to hot-add vTPM")
    cspec = vim.vm.ConfigSpec()
    AddVTPM(cspec)
    try:
        vm.Reconfigure(vm1, cspec)
        raise Exception("TPM hot-add did not raise exception")
    except vim.fault.InvalidPowerState as e:
        pass
    CheckTPMNotPresent(vm1)

def TestVTPMAddInUnsupportedHWVersion(vm1):
    Log("Trying to add vTPM to unsupported hwversion")
    cspec = vim.vm.ConfigSpec()
    AddVTPM(cspec)
    try:
        vm.Reconfigure(vm1, cspec)
        raise Exception("TPM added to vm with unsupported hwversion did not raise exception")
    except vim.fault.GenericVmConfigFault as e:
        pass
    CheckTPMNotPresent(vm1)

def TestVTPMRemoveDev(vm1, dev):
    cspec = vim.vm.ConfigSpec()
    vmconfig.AddDeviceToSpec(cspec, dev,
                             vim.vm.device.VirtualDeviceSpec.Operation.remove)
    vm.Reconfigure(vm1, cspec)
    CheckTPMNotPresent(vm1)

def TestNoVTPMRemoveDev(vm1, dev, fault=vim.fault.InvalidDeviceSpec):
    cspec = vim.vm.ConfigSpec()
    vmconfig.AddDeviceToSpec(cspec, dev,
                             vim.vm.device.VirtualDeviceSpec.Operation.remove)
    try:
        vm.Reconfigure(vm1, cspec)
        raise Exception("Reconfigure for TPM %s did not raise exception" %
                        cspec)
    except fault as e:
        pass

def TestNoVTPMRemoveKey(vm1, key):
    Log("Trying to remove vTPM with key %s" % key)
    TestNoVTPMRemoveDev(vm1, CreateVTPM(key))

def TestNoVTPMRemoveVDKey(vm1, key):
    Log("Trying to remove virtual device with key %s" % key)
    TestNoVTPMRemoveDev(vm1, CreateVD(key))

def TestVTPMRemoveInvalid(vm1):
    TestNoVTPMRemoveKey(vm1, 11001)
    TestNoVTPMRemoveKey(vm1, -1)
    TestNoVTPMRemoveKey(vm1, 0)
    TestNoVTPMRemoveKey(vm1, 100)
    TestNoVTPMRemoveKey(vm1, 1000)
    TestNoVTPMRemoveVDKey(vm1, 11001)
    TestNoVTPMRemoveVDKey(vm1, -1)

def TestNoVTPMRemove(vm1):
    TestNoVTPMRemoveKey(vm1, 11000)
    TestNoVTPMRemoveVDKey(vm1, 11000)
    TestVTPMRemoveInvalid(vm1)
    CheckTPMNotPresent(vm1)

def TestVTPMMove(vm1, key):
    Log("Replacing vTPM device with new key=%s" % key)
    cspec = vim.vm.ConfigSpec()
    vmconfig.AddDeviceToSpec(cspec, CreateVTPM(TPM_DEV_KEY),
                             vim.vm.device.VirtualDeviceSpec.Operation.remove)
    vmconfig.AddDeviceToSpec(cspec, CreateVTPM(key),
                             vim.vm.device.VirtualDeviceSpec.Operation.add)
    vm.Reconfigure(vm1, cspec)
    CheckTPMPresent(vm1)

def TestEK(vm1, val, fault, expected=None):
    tpm = CreateVTPM(TPM_DEV_KEY)
    if val is not None:
        val = [VmomiSupport.binary(v) for v in val]
        tpm.endorsementKeyCertificate = val
    Log("Trying to set EK certificate to '%s'" % val)
    cspec = vim.vm.ConfigSpec()
    vmconfig.AddDeviceToSpec(cspec, tpm,
                             vim.vm.device.VirtualDeviceSpec.Operation.edit)
    if fault is None:
        vm.Reconfigure(vm1, cspec)
    else:
        try:
            vm.Reconfigure(vm1, cspec)
            raise Exception("Reconfigure did not fail for %s" % cspec)
        except vim.fault.GenericVmConfigFault as e:
            ok = False
            for m in e.faultMessage:
                if m.key == fault:
                    ok = True
            if not ok:
                raise
        except vmodl.fault.InvalidArgument as e:
            if e.invalidProperty != fault:
                raise
    tpm = CheckTPMPresent(vm1)
    if expected is None:
        expected = val
    ekc = tpm.endorsementKeyCertificate
    if len(expected) != len(ekc):
        raise Exception("After setting EK to '%s', it is '%s'" %
                        (val, ekc))
    for l, r in zip(expected, ekc):
        if l != r:
            raise Exception("After setting EK to '%s', it is '%s'" %
                           (val, ekc))

def TestVTPMProps(vm1):
    tpm = CheckTPMPresent(vm1)
    goodCerts = tpm.endorsementKeyCertificate
    if len(goodCerts) == 0:
        raise Exception("TPM did not generate self-signed certificates")
    val = [ goodCerts[0] ]
    TestEK(vm1, val, None)
    TestEK(vm1, [b""], 'msg.vtpm.ekcrt.empty', val)
    TestEK(vm1, [b"M000"], 'endorsementKeyCertificate', val)
    TestEK(vm1, [b"\x30\x01"], 'endorsementKeyCertificate', val)
    TestEK(vm1, [b"\x30\x00\x30\x00"], 'endorsementKeyCertificate', val)
    TestEK(vm1, None, None, val)
    TestEK(vm1, [b"\x30\x00", b"\x30\x00", b"\x30\x00", b"\x30\x02"],
          'endorsementKeyCertificate', val)
    prev = val
    for c in goodCerts:
        crts = [ c ]
        TestEK(vm1, crts, None)
        prev = crts
    TestEK(vm1, goodCerts, None)
    first = goodCerts[0]
    mangled = first[:40] + bytes([first[40] ^ 1]) + first[41:]
    TestEK(vm1, [mangled], 'msg.vtpm.ekcrt.mismatch', goodCerts)
    TestEK(vm1, [mangled] + goodCerts[1:], 'msg.vtpm.ekcrt.mismatch', goodCerts)
    TestEK(vm1, [first, first], 'msg.vtpm.ekcrt.mismatch', goodCerts)

def TestVTPMHotRemove(vm1):
    Log("Trying to hot-remove vTPM")
    TestNoVTPMRemoveDev(vm1, CreateVTPM(TPM_DEV_KEY),
                        vim.fault.InvalidPowerState)
    CheckTPMPresent(vm1)

    Log("Trying to hot-remove virtual device with vTPM key")
    TestNoVTPMRemoveDev(vm1, CreateVD(TPM_DEV_KEY),
                        vim.fault.InvalidPowerState)
    CheckTPMPresent(vm1)

def TestNoVTPMRunning(vm1):
    TestVTPMHotAdd(vm1)
    TestNoVTPMRemove(vm1)

def TestNoVTPM(vm1):
    """
    Test that hot-add of vTPM fails
    """
    CheckTPMNotPresent(vm1)
    TestNoVTPMRemove(vm1)
    vm.PowerOn(vm1)
    try:
        TestNoVTPMRunning(vm1)
    finally:
        vm.PowerOff(vm1)

def TestVTPMReconfig(vm1):
    """
    Test add and remove for vTPM controller
    """
    Log("Adding vTPM")
    cspec = vim.vm.ConfigSpec()
    AddVTPM(cspec)
    vm.Reconfigure(vm1, cspec)
    CheckTPMPresent(vm1)
    TestAdd2ndTPM(vm1)
    TestVTPMRemoveInvalid(vm1)
    CheckTPMPresent(vm1)
    TestVTPMMove(vm1, -1)
    TestVTPMMove(vm1, TPM_DEV_KEY)
    TestVTPMMove(vm1, 100)
    TestVTPMProps(vm1)

    vm.PowerOn(vm1)
    try:
        TestVTPMProps(vm1)
        TestVTPMRemoveInvalid(vm1)
        TestVTPMHotRemove(vm1)
    finally:
        vm.PowerOff(vm1)
    # Remove TPM controller from VM
    Log("Removing TPM device from VM")
    TestVTPMRemoveDev(vm1, CreateVTPM(TPM_DEV_KEY))

def TestVTPMVDRemove(vm1):
    """
    Test vTPM removal via key
    """
    Log("Adding vTPM with positive key")
    cspec = vim.vm.ConfigSpec()
    AddVTPM(cspec, key=TPM_DEV_KEY)
    vm.Reconfigure(vm1, cspec)
    CheckTPMPresent(vm1)

    Log("Removing vTPM device from VM using virtual device with vTPM key")
    TestVTPMRemoveDev(vm1, CreateVD(TPM_DEV_KEY))

def CreateKeyForVM(si):
    # Pick a well known key so that we can more easily debug.
    # To add this key to an ESX host manually run,
    #   $VMTREE/support/scripts/vim-crypto-util keys add \
    #       -d "mxeZ/HG3itSGTRP3fEPxFLD0r/3HckVlHZAaplRoSxo=" \
    #       TestVTPMKey
    keyId     = "TestVTPMKey"
    data      = "mxeZ/HG3itSGTRP3fEPxFLD0r/3HckVlHZAaplRoSxo="
    cryptoKey = vimcrypto.CreateCryptoKeyPlain("TestVTPMKey", None, data=data)
    return keyId, cryptoKey

def AddEfiFirmware(cspec):
    cspec.firmware = vim.Vm.GuestOsDescriptor.FirmwareType.efi
    cspec.bootOptions = vim.vm.BootOptions()
    cspec.bootOptions.efiSecureBootEnabled = True

def CreateDummyEfiVM(vmname, hwversion="vmx-14", addVtpm=False, keyId=None):
    cfg = vm.CreateQuickDummySpec(vmname, vmxVersion = hwversion,
                                  guest = "otherGuest")
    AddEfiFirmware(cfg)
    if addVtpm:
        cryptoSpec = vimcrypto.CreateCryptoSpecEncrypt(keyId, None)
        cfg.crypto = cryptoSpec
        AddVTPM(cfg)

    return vm.CreateFromSpec(cfg)

def main():
    supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                    (["u:", "user="], "root", "User name", "user"),
                    (["p:", "pwd="], "", "Password", "pwd"),
                    (["v:", "vmname="], "VTPMTest",
                     "Name of the virtual machine", "vmname") ]

    supportedToggles = [ (["usage", "help"], False,
                         "Show usage information", "usage"),
                       (["runall", "r"], True, "Run all the tests", "runall"),
                       (["nodelete"], False,
                         "Dont delete vm on completion", "nodelete") ]

    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    if args.GetKeyValue("usage") == True:
        args.Usage()
        sys.exit(0)

    # Connect
    si = SmartConnect(host=args.GetKeyValue("host"),
                      user=args.GetKeyValue("user"),
                      pwd=args.GetKeyValue("pwd"))
    atexit.register(Disconnect, si)

    # Process command line
    vmname = args.GetKeyValue("vmname")
    runall = args.GetKeyValue("runall")
    noDelete = args.GetKeyValue("nodelete")
    status = "PASS"
    vm1 = None
    vm2 = None

    try:
        Log("Cleaning up VMs from previous runs...")
        vm.Delete(vmname, True)

        Log("Prepare host for crypto...")
        vimcrypto.CryptoEnableHost(host.GetHostSystem(si))

        Log("Adding key for encrypted VM...")
        cryptoMgr = si.RetrieveContent().cryptoManager
        keyId, cryptoKey = CreateKeyForVM(si)
        cryptoMgr.AddKeys([cryptoKey])

        ## vTPM requires hardware version 14+.
        Log("Creating Hw14 VM...")
        vm1 = CreateDummyEfiVM(vmname, addVtpm=True, keyId=keyId)
        TestVTPMProps(vm1)
        task = vm1.Destroy()
        WaitForTask(task)
        vm1 = None

        vm1 = CreateDummyEfiVM(vmname)

        Log("Encrypting VM...")
        vimcrypto.EncryptVM(vm1, keyId, None, disks=False)

        TestVTPMReconfig(vm1)
        TestNoVTPM(vm1)
        TestVTPMVDRemove(vm1)

        ## Test on unsupported HW
        Log("Creating Hw13 VM...")
        vm2 = CreateDummyEfiVM(vmname, hwversion="vmx-13")
        TestVTPMAddInUnsupportedHWVersion(vm2)

        Log("Tests completed.")

    except Exception as e:
        status = "FAIL"
        Log("Caught exception : %s, %r" % (e, e))
        raise
    finally:
        # Delete the vm as cleanup
        if noDelete == False:
            for v in [vm1, vm2]:
                if v != None:
                    task = v.Destroy()
                    WaitForTask(task)
                    v = None
    Log("TEST RUN COMPLETE: " + status)


# Start program
if __name__ == "__main__":
    main()

