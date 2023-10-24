## @file integtest.py
## @brief Various extensions to the PyUnit framework (module unittest).
##
## Detailed description (for Doxygen goes here)

## @package integtest
## @brief Various extensions to the PyUnit framework (module unittest).
"""
Various extensions to the PyUnit framework (module unittest).

Detailed description (for pydoc goes here)
"""

import sys
import os
import unittest
import testoob
import logging
from pyVim import folder
from pyVim import vm
from pyVim import connect
from pyVim import invt
from pyVim import host
from pyVim import vimhost
from pyVmomi import Vim, VmomiSupport


##
## @brief Replacements and extensions for the unittest.TestCase class.
##
class TestCase(unittest.TestCase):
    """
    Replacements and extensions for the unittest.TestCase class.
    """
    def failUnlessRaises(self, message, exceptionClass, callableObj, *args,
                         **kwargs):
        """
        A replacement failUnlessRaises.
        unittest.failUnlessRaises() doesn't work with Vim objects.
        ex: self.failUnlessRaises(Vim.Fault.InvalidPowerState, vm.Suspend, tmsg)
        will try for attributes: __name__ and if not set uses str(fault) instead
        of returning the name of the fault this test was expecting.
        """
        from testoob.utils import _pop
        from testoob.testing import TestoobAssertionError, _call_signature
        expectedArgs = _pop(kwargs, "expectedArgs", None)
        expectedRegex = _pop(kwargs, "expectedRegex", None)

        def callsig():
            """Return call signature."""
            return _call_signature(callableObj, *args, **kwargs)

        def exc_name():
            """Return exception class name."""
            if hasattr(exceptionClass, '__name__'):
                exception_name = exceptionClass.__name__
            elif hasattr(exceptionClass, '_typeName'):
                exception_name = exceptionClass._typeName
            else:
                exception_name = str(exceptionClass)
            return exception_name

        try:
            callableObj(*args, **kwargs)
        except exceptionClass as e:
            if expectedArgs is not None:
                testoob.assert_equals(
                      expectedArgs, e.args,
                      msg="%s; %s raised %s with unexpected args: " \
                          "expected=%r, actual=%r" % \
                          (message, callsig(), e.__class__, expectedArgs, e.args)
                   )
            if expectedRegex is not None:
                testoob.assert_matches(
                      expectedRegex, str(e),
                      msg="%s; %s raised %s, but the regular expression '%s' " \
                          "doesn't match %r" % \
                          (message, callsig(), e.__class__, expectedRegex, str(e))
                   )
        except:
            msg = "%s; %s raised an unexpected exception type: " \
                  "expected=%s, actual=%s" % \
                  (message, callsig(), exc_name(), sys.exc_info()[0])
            raise TestoobAssertionError(msg,
                                        description="failUnlessRaises failed")
        else:
            raise TestoobAssertionError(
                  "%s; %s not raised" % \
                  (message, exc_name()), description="failUnlessRaises failed")

    def failIfRaises(self, message, callableObj, *args, **kwargs):
        """ Deal with void functions that use exceptions to report failure. """
        try:
            callableObj(*args, **kwargs)
            return True
        except Exception as msg:
            raise self.failureException("%s; %s" % (message,
                               msg or 'unexpected exception %s %s' % \
                               (message, msg.__class__)))

    # Synonyms for assertion methods to be consistent with PyUnit library.
    assertRaises = failUnlessRaises
    assertNotRaises = failIfRaises


def _import(module_name, class_name):
    """
    Return class of the module_name, where module_name is of the form
    package.module (testoob's Asserter, which does simple __import__, returns
    package, not package.module in this situation).
    """
    mod = __import__(module_name)
    components = module_name.split('.')
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return getattr(mod, class_name)


def RegisterAsserters():
    module_name = "pyVim.integtest"
    class_name = "TestCase"
    methods_pattern = "(^assert)|(^fail[A-Z])|(^fail$)"

    Class = _import(module_name, class_name)
    from re import match
    from testoob.asserter import Asserter
    for method_name in dir(Class):
        if match(methods_pattern, method_name):
            Asserter()._make_assert_report(Class, method_name)


##
## @brief This fixture creates and destroys a test VM.
##
class FixtureCreateDummyVM(TestCase):
    """ This fixture creates and destroys a test VM. """
    def destroyTestVM(self, vmname):
        """ Powers down the VM if needed and then destroys it. """
        existing_vm = folder.Find(vmname)
        if existing_vm is not None:
            if vm.VM(existing_vm, None, None).IsRunning():
                vm.PowerOff(existing_vm)
            existing_vm.Destroy()
            self._vm = None

    def setUp(self):
        """ Connects to the host and creates test VM. """
        self._host = vimhost.Host()
        connect.SetSi(self._host._si)
        # Create dummy test VM
        self._vmname = "ttt.%s" % str(self.__class__.__module__)
        if (self._vmname is None):
            raise self.failureException(
                "Test VM name is not a valid path name. %s" % (self._vmname))
        try:
            self.destroyTestVM(self._vmname)
            envBrowser = invt.GetEnv()
            cfgTarget = envBrowser.QueryConfigTarget(None)
            if len(cfgTarget.GetDatastore()) == 0:
                cm = host.GetHostConfigManager(self._si)
                dsm = cm.GetDatastoreSystem()
                # todo is this going to work on vmkernel
                dsm.CreateLocalDatastore("tttds1", "/var/tmp")

            # create a quick dummy test VM with one SCSI disk
            self._vm = vm.CreateQuickDummy(self._vmname, 1)
            vm1 = vm.VM(self._vm, None, None)
            if (not vm1.IsPoweredOff()):
                raise self.failureException(
                    "Newly created test VM should be powered off.")
        except Exception as msg:
            raise self.failureException(
                "Failed to create test VM \"%s\" on host=\"%s\": %s" %
                (self._vmname, self._host, msg))
        print("INFO: created vm %s " % (self._vmname))

    def tearDown(self):
        """ Destroys test VM. """
        self._si = None

        self.destroyTestVM(self._vmname)
        existing_vm = folder.Find(self._vmname)
        if (existing_vm is not None):
            raise self.failureException("Test VM should have been destroyed.")
        print("INFO: destroyed vm %s " % (self._vmname))
