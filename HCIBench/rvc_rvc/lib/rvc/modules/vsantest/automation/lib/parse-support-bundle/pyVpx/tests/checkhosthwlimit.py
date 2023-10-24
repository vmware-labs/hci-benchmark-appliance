#!/usr/bin/python

from __future__ import print_function

import sys
import ssl
import atexit

from pyVmomi import Vim
from pyVmomi import Vmodl
from pyVim.connect import SmartConnect, Disconnect
from pyVim.helpers import Log
from pyVim import arguments
from pyVim import invt
from pyVim import vimutil

status = 'PASS'

def Error(msg):
    global status

    status = 'FAIL'
    Log("ERROR: %s" % msg)

def Reconfigure(cr, defaultVersion=None, maxVersion=None, modify=False):
    val = Vim.ComputeResource.ConfigSpec()
    if defaultVersion is not None:
        val.SetDefaultHardwareVersionKey(defaultVersion)
    if maxVersion is not None:
        val.SetMaximumHardwareVersionKey(maxVersion)
    Log("Checking %.10s, %.10s" % (defaultVersion, maxVersion))
    vimutil.InvokeAndTrack(cr.ReconfigureEx, val, modify)

def CheckConfig(cr, defaultVersion, maxVersion):
    curr = cr.GetConfigurationEx()
    if curr.GetDefaultHardwareVersionKey() != defaultVersion and \
       (defaultVersion is not None or curr.GetDefaultHardwareVersionKey()):
        Error("Expected default %s, got %s" %
              (defaultVersion, curr.GetDefaultHardwareVersionKey()))
    if curr.GetMaximumHardwareVersionKey() != maxVersion and \
       (maxVersion is not None or curr.GetMaximumHardwareVersionKey()):
        Error("Expected maximum %s, got %s" %
              (maxVersion, curr.GetMaximumHardwareVersionKey()))

def GetVersions(cr):
    environmentBrowser = cr.GetEnvironmentBrowser()
    assert environmentBrowser is not None
    foundDefault = None
    foundVersions = set()
    versions = environmentBrowser.QueryConfigOptionDescriptor()
    for version in versions:
        k = version.GetKey()
        if k in foundVersions:
            Error("%s is present multiple times" % k)
        if version.GetDefaultConfigOption():
            if foundDefault is not None:
                Error("%s and %s are both default" % (k, foundDefault))
            foundDefault = k
        foundVersions.add(k)
    if foundDefault is None:
        Error("No default version found")
    return (foundDefault, foundVersions)

def CheckEnvironmentBrowser(cr, defaultVersion, maxVersion):
    environmentBrowser = cr.GetEnvironmentBrowser()
    if environmentBrowser is None:
        Log("No environment browser")
    else:
        foundDefault = None
        foundVersions = {}
        versions = environmentBrowser.QueryConfigOptionDescriptor()
        for version in versions:
            k = version.GetKey()
            if k in foundVersions:
                Error("%s is present multiple times" % k)
            if version.GetDefaultConfigOption():
                if foundDefault is not None:
                    Error("%s and %s are both default" % (k, foundDefault))
                foundDefault = k
            co = environmentBrowser.QueryConfigOption(k, None)
            foundVersions[k] = co
            if maxVersion is not None and co.version > maxVersion:
                Error("%s should be hidden, but is not" %  k)
        if defaultVersion is not None:
            if defaultVersion == foundDefault:
                Log("OK, default version is %s" % foundDefault)
            else:
                Error("Default should be %s, but is %s" %
                      (defaultVersion, foundDefault))
        else:
            Log("Default version is %s" % (foundDefault))
        co = environmentBrowser.QueryConfigOption(None, None)
        if foundDefault is None:
            Error("No default version set")
        else:
            if str(co) != str(foundVersions[foundDefault]):
                Error("Default implicit config option does not match "
                      "default explicit config option")
            else:
                Log("OK, all good")
        Log("Found configs %s" % ', '.join(sorted(foundVersions.keys())))


def main():
    global status

    supportedArgs = [(["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd")]

    supportedToggles = [(["usage", "help"], False,
                         "Show usage information", "usage")]

    args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
    if args.GetKeyValue("usage"):
        args.Usage()
        sys.exit(0)

    # Connect
    si = SmartConnect(host=args.GetKeyValue("host"),
                      user=args.GetKeyValue("user"),
                      pwd=args.GetKeyValue("pwd"),
                      sslContext=ssl._create_unverified_context())
    atexit.register(Disconnect, si)

    content = si.RetrieveContent()
    isVC = content.GetAbout().GetApiType() == "VirtualCenter"
 

    # Process command line
    cr = invt.GetHostFolder().GetChildEntity()[0]
    curr = cr.GetConfigurationEx()

    # Set host into the default configuration
    Reconfigure(cr, '', '', True)
    CheckConfig(cr, None, None)
    (productDefault, productVersions) = GetVersions(cr)
    productMax = sorted(productVersions)[-1]

    bogusVersions = ['bogus', 'vmx-00', 'vmx-99', 'vmx-100',
                     'x' * 255, 'x' * 256, 'x' * 511, 'x' * 512]
    testVersions = [''] + bogusVersions + list(productVersions)
    for defVer in sorted(testVersions):
        for maxVer in sorted(testVersions):
            # Invalid maximum version is fatal.
            # Invalid default version is ignored for backward compatibility
            # vCenter rejects default version longer than 255 due to DB
            #     schema restriction
            shouldFail = maxVer in bogusVersions
            if isVC:
                shouldFail |= len(defVer) > 255
            curr = cr.GetConfigurationEx()
            try:
                Reconfigure(cr, defVer, maxVer, True)
                if shouldFail:
                   Error('Unexpected success')
                # Long default version succeeds, but does nothing...
                if len(defVer) >= 512:
                    curr2 = cr.GetConfigurationEx()
                    if str(curr) != str(curr2):
                        Error("Configuration changed on error, from %s to %s" %
                              (curr, curr2))
                    expectDefVer = curr.GetDefaultHardwareVersionKey()
                    expectMaxVer = curr.GetMaximumHardwareVersionKey()
                else:
                    if defVer == '':
                       expectDefVer = None
                    else:
                        expectDefVer = defVer
                    if maxVer == '':
                        expectMaxVer = None
                    else:
                        expectMaxVer = maxVer
                    CheckConfig(cr, expectDefVer, expectMaxVer)
            except Vmodl.Fault.InvalidArgument:
                if not shouldFail:
                    Error('Unexpected invalid argument')
                curr2 = cr.GetConfigurationEx()
                if str(curr) != str(curr2):
                    Error("Configuration changed on error, from %s to %s" %
                          (curr, curr2))
                expectDefVer = curr.GetDefaultHardwareVersionKey()
                expectMaxVer = curr.GetMaximumHardwareVersionKey()
                    
            (fDef, fVers) = GetVersions(cr)
            if expectDefVer not in productVersions:
                expectDefVer = productDefault
            if expectMaxVer is not None and \
               expectMaxVer in productVersions and \
               int(expectMaxVer[4:]) < int(expectDefVer[4:]):
                expectDefVer = expectMaxVer
            if fDef != expectDefVer:
                Error('Default version should be %s, but is %s' %
                      (expectDefVer, fDef))
            if expectMaxVer is None:
                if fVers != productVersions:
                    Error('Supported versions %s does not match known versions %s' %
                          (', '.join(fVers), ', '.join(productVersions)))
            else:
                if not fVers.issubset(productVersions):
                    Error('Supported versions %s are not subset of known versions %s' %
                          (', '.join(fVers), ', '.join(productVersions)))
                diff = productVersions.difference(fVers)
                for v in diff:
                    if v <= expectMaxVer:
                        Error('Supported version %s is missing from the supported list' %
                              v)

    Reconfigure(cr, 'vmx-12', '', True)
    CheckConfig(cr, 'vmx-12', None)
    (fDef, fVers) = GetVersions(cr)
    assert fDef == 'vmx-12'
    assert fVers == productVersions
    CheckEnvironmentBrowser(cr, 'vmx-12', productMax)

    Reconfigure(cr, None, 'vmx-11', True)
    CheckConfig(cr, 'vmx-12', 'vmx-11')
    (fDef, fVers) = GetVersions(cr)
    assert fDef == 'vmx-11'
    CheckEnvironmentBrowser(cr, 'vmx-11', 'vmx-11')

    Reconfigure(cr, 'vmx-14', None, True)
    CheckConfig(cr, 'vmx-14', 'vmx-11')
    (fDef, fVers) = GetVersions(cr)
    assert fDef == 'vmx-11'
    CheckEnvironmentBrowser(cr, 'vmx-11', 'vmx-11')

    Reconfigure(cr, None, 'vmx-14', True)
    CheckConfig(cr, 'vmx-14', 'vmx-14')
    (fDef, fVers) = GetVersions(cr)
    assert fDef == 'vmx-14'
    CheckEnvironmentBrowser(cr, 'vmx-14', 'vmx-14')

    Reconfigure(cr, None, '', True)
    CheckConfig(cr, 'vmx-14', None)
    (fDef, fVers) = GetVersions(cr)
    assert fDef == 'vmx-14'
    assert fVers == productVersions
    CheckEnvironmentBrowser(cr, 'vmx-14', productMax)

    Reconfigure(cr, 'vmx-12', 'vmx-11', True)
    CheckConfig(cr, 'vmx-12', 'vmx-11')
    (fDef, fVers) = GetVersions(cr)
    assert fDef == 'vmx-11'
    CheckEnvironmentBrowser(cr, 'vmx-11', 'vmx-11')

    if isVC:
       # vCenter actually does not support replacing
       # cluster configuration.
       Reconfigure(cr, "", "", False)
    else:
       Reconfigure(cr, None, None, False)
    CheckConfig(cr, None, None)
    (fDef, fVers) = GetVersions(cr)
    if fDef != productDefault:
        Error('Expected default %s, got %s' % (productDefault, fDef))
    if fVers != productVersions:
        Error('Expected list %s, got %s' % (productVersions, fVers))
    CheckEnvironmentBrowser(cr, productDefault, productMax)
    Log("TEST RUN COMPLETE: %s" %  status)



# Start program
if __name__ == "__main__":
    main()
