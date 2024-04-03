## @file vimcrypto.py
## @brief Vim Crypto Helpers
##
## Detailed description (for Doxygen goes here)
"""
Vim Crypto Helpers

A set of Vim wrappers that make it easier to work with vim.encryption
objects and the related operations.

"""

__author__ = "VMware, Inc"

import base64
import os
import sys
import uuid

from pyVmomi import Vim
from pyVim import vm, vmconfig

#
# Vim.Encryption utility functions
#


def CreateKey(bits=256):
    """Create a key that is suitible for test purposes.

    This function creates a random key that can be used as the key
    for virtual machine configuration or virtual disk descriptor
    encryption in test environments. The key is base64 encoded, as
    expected by the Vim APIs.

    Note that this approach must not be used in production.
    """
    if bits == 0 or bits % 8 != 0:
        raise ValueError("Invalid number of bits: %d" % bits)

    # XXX Cleanup once Python 2 is gone.
    if (sys.version_info >= (3, 0)):
        rbytes = os.urandom(int(bits / 8))
        return base64.b64encode(rbytes).decode('utf-8')
    else:
        return base64.b64encode(os.urandom(bits / 8))


def GetAlgorithmBits(algo):
    if algo == "AES-256":
        return 256
    if algo == "XTS-AES-256":
        return 512
    raise ValueError("Unknown algorithm: %s" % algo)


def CreateCryptoKeyPlain(keyId, providerId, algo="AES-256", data=None):
    cryptoKey = Vim.Encryption.CryptoKeyPlain()
    cryptoKey.SetKeyId(CreateCryptoKeyId(keyId, providerId))
    cryptoKey.SetAlgorithm(algo)
    if not data:
        data = CreateKey(GetAlgorithmBits(algo))
    cryptoKey.SetKeyData(data)
    return cryptoKey


def CreateCryptoKeyDefault(algo="AES-256"):
    keyId = uuid.uuid4().hex
    providerId = "Test.%d" % os.getpid()
    cryptoKey = CreateCryptoKeyPlain(keyId, providerId, algo)
    return keyId, providerId, cryptoKey


def CreateCryptoHostKeyDefault():
    keyId = "VMwareInternalHostKeyForTesting"
    algo = "AES-256"
    data = "mxeZ/HG3itSGTRP3fEPxFLD0r/3HckVlHZAaplRoSxo="
    return keyId, None, CreateCryptoKeyPlain(keyId, None, algo, data)


def CreateCryptoKeyId(keyId, providerId):
    cryptoKeyId = Vim.Encryption.CryptoKeyId()
    cryptoKeyId.SetKeyId(keyId)
    if providerId:
        keyProviderId = Vim.Encryption.KeyProviderId()
        keyProviderId.SetId(providerId)
        cryptoKeyId.SetProviderId(keyProviderId)
    return cryptoKeyId


def CreateCryptoSpecEncrypt(keyId, providerId):
    cryptoSpec = Vim.Encryption.CryptoSpecEncrypt()
    cryptoSpec.SetCryptoKeyId(CreateCryptoKeyId(keyId, providerId))
    return cryptoSpec


def CreateCryptoSpecDecrypt():
    return Vim.Encryption.CryptoSpecDecrypt()


def CreateCryptoSpecRecrypt(keyId, providerId):
    cryptoSpec = Vim.Encryption.CryptoSpecDeepRecrypt()
    cryptoSpec.SetNewKeyId(CreateCryptoKeyId(keyId, providerId))
    return cryptoSpec


def CreateCryptoSpecRekey(keyId, providerId):
    cryptoSpec = Vim.Encryption.CryptoSpecShallowRecrypt()
    cryptoSpec.SetNewKeyId(CreateCryptoKeyId(keyId, providerId))
    return cryptoSpec


def CreateCryptoSpecNoOp():
    return Vim.Encryption.CryptoSpecNoOp()


def CreateCryptoSpecRegister(keyId, providerId):
    cryptoSpec = Vim.Encryption.CryptoSpecRegister()
    if keyId:
        cryptoSpec.SetCryptoKeyId(CreateCryptoKeyId(keyId, providerId))
    return cryptoSpec


def MatchCryptoKeyId(keyId1, keyId2):
    if keyId1.keyId != keyId2.keyId:
        return False
    if (keyId1.providerId and not keyId2.providerId
            or not keyId1.providerId and keyId2.providerId):
        return False
    if (keyId1.providerId and keyId2.providerId
            and keyId1.providerId.id != keyId2.providerId.id):
        return False
    return True


def CryptoEnableHost(hostSystem):
    # The current host key will be updated to the default one.
    if hostSystem.runtime.cryptoState == "incapable":
        hostSystem.PrepareCrypto()
    keyId, providerId, cryptoKey = CreateCryptoHostKeyDefault()
    hostSystem.EnableCrypto(cryptoKey)


#
# Storage policy helpers
#

_vmcryptVib = "VMW_vmwarevmcrypt_1.0.0"

_policyHeader = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
                 "<storageProfile xsi:type=\"StorageProfile\">"
                 "<constraints><subProfiles>")
_policyFooter = ("<name>Rule-Set 1: IOFILTERS</name>"
                 "</subProfiles></constraints>"
                 "<createdBy>None</createdBy>"
                 "<creationTime>1970-01-01T00:00:00Z</creationTime>"
                 "<lastUpdatedTime>1970-01-01T00:00:00Z</lastUpdatedTime>"
                 "<generationId>1</generationId>"
                 "<name>None</name>"
                 "<profileId>Phony Profile ID</profileId>"
                 "</storageProfile>")
_policyVMcrypt = ("<capability><capabilityId>"
                  "<id>vmwarevmcrypt@encryption</id>"
                  "<namespace>IOFILTERS</namespace>"
                  "<constraint></constraint>"
                  "</capabilityId></capability>")
_policyCrypto = _policyHeader + _policyVMcrypt + _policyFooter
_policyNone = _policyHeader + _policyFooter


def DefaultCryptoPolicy():
    return _policyCrypto


def DefaultEmptyPolicy():
    return _policyNone


#
# Verification utility functions
#


def _IsEncrypted(obj, keyId, providerId):
    if not obj.keyId:
        return False
    if obj.keyId.keyId != keyId:
        return False
    if (providerId and not obj.keyId.providerId
            or not providerId and obj.keyId.providerId):
        return False
    if providerId and providerId != obj.keyId.providerId.id:
        return False
    return True


def VerifyEncrypted(obj, keyId, providerId):
    if not obj.keyId:
        raise Exception("Object not encrypted.")
    if obj.keyId.keyId != keyId:
        raise Exception("Object encrypted with wrong keyId.")
    if (providerId and not obj.keyId.providerId
            or not providerId and obj.keyId.providerId):
        raise Exception("Unexpected object key provider ID.")
    if providerId and obj.keyId.providerId.id != providerId:
        raise Exception("Object encrypted with wrong providerId.")


def VerifyNotEncrypted(obj):
    if obj.keyId:
        raise Exception("Object is encrypted.")


def _VerifyEncryptedDiskParent(parent, keyId, providerId, encrypted=True):
    if parent:
        if encrypted != _IsEncrypted(parent, keyId, providerId):
            raise Exception("Unexpected parent encryption")
        _VerifyEncryptedDiskParent(parent.parent, keyId, providerId, encrypted)


def VerifyEncryptedDisksConfig(config, keyId, providerId, expect=1):
    count = 0
    for device in config.hardware.device:
        if isinstance(device, Vim.Vm.Device.VirtualDisk):
            if _IsEncrypted(device.backing, keyId, providerId):
                if not _vmcryptVib in device.iofilter:
                    raise Exception("Encryption filter not configured.")
                _VerifyEncryptedDiskParent(device.backing.parent, keyId,
                                           providerId)
                count += 1

    if count != expect:
        raise Exception("Expected %d encrypted disks; found %d." %
                        (expect, count))


def VerifyAllEncryptedDisksConfig(config, keyId, providerId):
    count = 0
    for device in config.hardware.device:
        if isinstance(device, Vim.Vm.Device.VirtualDisk):
            count += 1
    assert not count == 0
    VerifyEncryptedDisksConfig(config, keyId, providerId, expect=count)


def VerifyEncryptedDisks(vm1, keyId, providerId, expect=1):
    VerifyEncryptedDisksConfig(vm1.config, keyId, providerId, expect)


def VerifyAllEncryptedDisks(vm1, keyId, providerId):
    VerifyAllEncryptedDisksConfig(vm1.config, keyId, providerId)


def VerifyNotEncryptedDisks(vm1):
    for device in vm1.config.hardware.device:
        if isinstance(device, Vim.Vm.Device.VirtualDisk):
            VerifyNotEncrypted(device.backing)
            if _vmcryptVib in device.iofilter:
                raise Exception("Unexpected encryption filter")
            _VerifyEncryptedDiskParent(device.backing.parent,
                                       None,
                                       None,
                                       encrypted=False)


#
# Virtual machine utility functions
#


def EncryptVM(vm1, keyId, providerId, disks=True):
    """Encrypt an entire VM and verify encrypted. """
    cryptoSpec = CreateCryptoSpecEncrypt(keyId, providerId)
    configSpec = Vim.Vm.ConfigSpec()
    configSpec.crypto = cryptoSpec

    count = 0
    if disks:
        for disk in vmconfig.CheckDevice(vm1.config,
                                         Vim.Vm.Device.VirtualDisk):
            assert not disk.backing.keyId
            op = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
            vmconfig.AddDeviceToSpec(configSpec,
                                     disk,
                                     op,
                                     policy=_policyCrypto,
                                     crypto=cryptoSpec)
            count += 1

    vm.Reconfigure(vm1, configSpec)
    VerifyEncrypted(vm1.config, keyId, providerId)
    VerifyEncryptedDisks(vm1, keyId, providerId, expect=count)


def DecryptVM(vm1, disks=True):
    """Decrypt an entire VM and verify not-encrypted. """
    cryptoSpec = CreateCryptoSpecDecrypt()
    configSpec = Vim.Vm.ConfigSpec()
    configSpec.crypto = cryptoSpec

    if disks:
        for disk in vmconfig.CheckDevice(vm1.config,
                                         Vim.Vm.Device.VirtualDisk):
            if not disk.backing.keyId:
                continue
            op = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
            vmconfig.AddDeviceToSpec(configSpec,
                                     disk,
                                     op,
                                     policy=_policyNone,
                                     crypto=cryptoSpec)

    vm.Reconfigure(vm1, configSpec)
    VerifyNotEncrypted(vm1.config)
    VerifyNotEncryptedDisks(vm1)


def ChangeVMEncryption(vm1, cryptoSpec, policy, disks=True):
    """Change the entire VM encryption based on cryptoSpec and policy. """
    configSpec = Vim.Vm.ConfigSpec()
    configSpec.crypto = cryptoSpec

    if disks:
        for disk in vmconfig.CheckDevice(vm1.config,
                                         Vim.Vm.Device.VirtualDisk):
            op = Vim.Vm.Device.VirtualDeviceSpec.Operation.edit
            vmconfig.AddDeviceToSpec(configSpec,
                                     disk,
                                     op,
                                     policy=policy,
                                     crypto=cryptoSpec)

    vm.Reconfigure(vm1, configSpec)
