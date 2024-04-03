#!/usr/bin/env python

__doc__ = """
@file case_1_PatchManager.py --
Copyright 2008-2014 VMware, Inc.  All rights reserved. -- VMware Confidential

This module verifies PatchManager functionality.
"""

__author__ = "VMware, Inc"

import os
import logging
from pyVim import integtest, connect, vimhost, vimutil
from pyVmomi import Vim, Vmodl

MetaUrls = [
#    "file:///exit26/home/dwang/vibs/build-vibs/depot-1/metadata.zip",
#    "file:///exit26/home/evan/vmkag-depot/depot/metadata.zip",
    "http://engweb.vmware.com/~swang/depot3/vmware/vmware-cos-metadata.zip",
    ]
BundleUrls = [
    "/exit26/home/evan/vibs/thirdparty/swordfish-071408.zip",
    ]
VibUrls = [
    "http://engweb.vmware.com/~swang/depot3/vmware/classic/ESX40-SIMPLE-01.vib",
    "http://engweb.vmware.com/~swang/depot3/vmware/classic/ESX40-SIMPLE-02.vib",
    "http://engweb.vmware.com/~swang/depot3/vmware/classic/ESX40-SIMPLE-03.vib",
    "http://engweb.vmware.com/~swang/depot3/vmware/classic/ESX40-SIMPLE-04.vib",
    "http://engweb.vmware.com/~swang/depot3/vmware/classic/ESX40-SIMPLE-05.vib",
    "http://engweb.vmware.com/~swang/depot3/vmware/classic/ESX40-SIMPLE-06.vib",
    "http://engweb.vmware.com/~swang/depot3/vmware/classic/ESX40-SIMPLE-07.vib",
    "http://engweb.vmware.com/~swang/depot3/vmware/classic/ESX40-SIMPLE-08.vib",
    "http://engweb.vmware.com/~swang/depot3/vmware/classic/ESX40-SIMPLE-09.vib",
    "http://engweb.vmware.com/~swang/depot3/vmware/classic/ESX40-SIMPLE-10.vib",
    ]

FAILED_VERSION_NUMBER = "-0.0"

class PatchManagerFixture(integtest.TestCase):
    """
    This test suite verifies PatchManager functionality.
    """
    def setUp(self):
        self._host = vimhost.Host()
        self._configManager = self._host.GetHostSystem().GetConfigManager()
        self.failIf(self._configManager is None,
                    "Expected valid ConfigManager.")
        self._patchManager = self._configManager.patchManager
        self.failIf(self._patchManager is None,
                    "Expected valid PatchManager.")

    def tearDown(self):
        self._host = None

    def InvokeAndTrack(self,
                       func,
                       *args,
                       **kw):
        self._result = None
        task = func(*args, **kw)
        self.failIfRaises(
            "Waiting for task expected not to raise.",
            vimutil.WaitForTask,
            task,
            pc=self._host.GetPropertyCollector()
            )
        info = task.GetInfo()
        if info is not None:
            self._result = info.GetResult()


class TestPositive(PatchManagerFixture):
    def test_Check(self):
        """
        Verify Check operation.
        """
        self.InvokeAndTrack(
            self._patchManager.Check,
            MetaUrls)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    def test_Check_OfflineBundle(self):
        """
        Verify Check operation.
        """
        self.InvokeAndTrack(
            self._patchManager.Check,
            None, BundleUrls)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    def test_ScanV2(self):
        """
        Verify ScanV2 operation.
        """
        self.InvokeAndTrack(
            self._patchManager.ScanV2,
            MetaUrls)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    def test_ScanV2_OfflineBundle(self):
        """
        Verify ScanV2 operation.
        """
        self.InvokeAndTrack(
            self._patchManager.ScanV2,
            None, BundleUrls)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    def test_Stage(self):
        """
        Verify Stage operation.
        """
        self.InvokeAndTrack(
            self._patchManager.Stage,
            MetaUrls, None, VibUrls)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    def test_Stage_OfflineBundle(self):
        """
        Verify Stage operation.
        """
        self.InvokeAndTrack(
            self._patchManager.Stage,
            None, BundleUrls, VibUrls)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    def test_InstallV2(self):
        """
        Verify InstallV2 operation.
        """
        self.InvokeAndTrack(
            self._patchManager.InstallV2,
            MetaUrls, None, VibUrls)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    def test_InstallV2_OfflineBundle(self):
        """
        Verify InstallV2 operation.
        """
        self.InvokeAndTrack(
            self._patchManager.InstallV2,
            None, BundleUrls, VibUrls)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    def test_InstallV2_NoSigCheck(self):
        """
        Verify InstallV2 operation.
        """
        spec = self._patchManager.PatchManagerOperationSpec()
        spec.cmdOption = "--nosigcheck"
        self.InvokeAndTrack(
            self._patchManager.InstallV2,
            MetaUrls, None, VibUrls, spec)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    def test_InstallV2_NoSigCheckAndMaintenanceMode(self):
        """
        Verify InstallV2 operation.
        """
        spec = self._patchManager.PatchManagerOperationSpec()
        spec.cmdOption = "--nosigcheck --maintenancemode"
        self.InvokeAndTrack(
            self._patchManager.InstallV2,
            MetaUrls, None, VibUrls, spec)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    def test_Query(self):
        """
        Verify Query operation.
        """
        self.InvokeAndTrack(self._patchManager.Query)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

class TestNegative(PatchManagerFixture):
    #def test_Check_NoDepotUrl(self):
    #    """
    #    Check, no depot url, should raise.
    #    """
    #    self.failUnlessRaises(
    #        "Check with empty metaUrl list should raise.",
    #        Vmodl.Fault.InvalidArgument,
    #        self.InvokeAndTrack,
    #        self._patchManager.Check,
    #        []
    #        )
    #    self.failUnless(self._result is None,
    #                    "Expected no results.")

    def test_Check_EmptyDepotUrl(self):
        """
        Check, empty depot url, should raise.
        """
        self.failUnlessRaises(
            "Check with empty meta url should raise.",
            Vmodl.Fault.InvalidArgument,
            self.InvokeAndTrack,
            self._patchManager.Check,
            ["",]
            )
        self.failUnless(self._result is None,
                        "Expected no results.")

    def test_Check_DepotUrlDoesntExist(self):
        """
        Check, bad depot url, the call should succeed.
        """
        self.InvokeAndTrack(
            self._patchManager.Check,
            ["file:///fake_location/metadata.zip",]
            )
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    #def test_ScanV2_NoDepotUrl(self):
    #    """
    #    ScanV2, no depot url passed.
    #    """
    #    self.failUnlessRaises(
    #        "ScanV2 with empty metaUrl list should raise.",
    #        Vmodl.Fault.InvalidArgument,
    #        self.InvokeAndTrack,
    #        self._patchManager.ScanV2,
    #        []
    #        )
    #    self.failUnless(self._result is None,
    #                    "Expected no results.")

    def test_ScanV2_EmptyDepotUrl(self):
        """
        Check, empty depot url, should raise.
        """
        self.failUnlessRaises(
            "ScanV2 with empty meta url should raise.",
            Vmodl.Fault.InvalidArgument,
            self.InvokeAndTrack,
            self._patchManager.ScanV2,
            ["",]
            )
        self.failUnless(self._result is None,
                        "Expected no results.")

    def test_ScanV2_DepotUrlDoesntExist(self):
        """
        Check, bad depot url, the call should succeed.
        """
        self.InvokeAndTrack(
            self._patchManager.ScanV2,
            ["file:///fake_location/metadata.zip",]
            )
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")


class TestCmdOption(PatchManagerFixture):
    def test_Stage_NoSig(self):
        """
        Verify Stage operation, no signature check.
        """
        spec = self._patchManager.PatchManagerOperationSpec()
        spec.cmdOption = "--nosigcheck"
        self.InvokeAndTrack(
            self._patchManager.Stage,
            MetaUrls, None, VibUrls, spec)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    def test_Stage_Maintenance(self):
        """
        Verify Stage operation, maintenance mode.
        """
        spec = self._patchManager.PatchManagerOperationSpec()
        spec.cmdOption = "--maintenancemode"
        self.InvokeAndTrack(
            self._patchManager.Stage,
            MetaUrls, None, VibUrls, spec)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

    def test_Stage_MultOptions(self):
        """
        Verify Stage operation, multiple options.
        """
        spec = self._patchManager.PatchManagerOperationSpec()
        spec.cmdOption = "--maintenancemode --nosigcheck"
        self.InvokeAndTrack(
            self._patchManager.Stage,
            MetaUrls, None, VibUrls, spec)
        self.failIf(self._result is None,
                    "Expected results.")
        self.failIf(self._result.GetXmlResult() == "",
                    "Expected non-empty results.")
        logging.debug(self._result.GetXmlResult())
        self.failIf(self._result.GetVersion() == FAILED_VERSION_NUMBER,
                    "Expected valid version number in an xml response.")

class TestObsolete(PatchManagerFixture):
    def test_Scan(self):
        """
        Scan, pre-K/L version.
        """
        locator = self._patchManager.Locator()
        locator.url = MetaUrls[0]
        self.InvokeAndTrack(
            self._patchManager.Scan,
            locator
            )
        # TODO: Actually, it looks like results COULD be empty
        # TODO: Need to check return code?
        self.failIf(len(self._result) == 0,
                    "Expected non-empty results array.")

        r = self._result[0]
        self.failIf(r.GetId() == "",
                    "Expected non-empty ID.")
        applicable = r.GetApplicable()
        self.failUnless(applicable == True or applicable == False,
                    "applicable: Expected True or False.")
        vmOffReq = r.GetVmOffRequired()
        self.failUnless(vmOffReq == True or vmOffReq == False,
                    "vmOffRequired: Expected True or False.")
        restartReq = r.GetRestartRequired()
        self.failUnless(restartReq == True or restartReq == False,
                    "restartRequired: Expected True or False.")
        # TODO: Check results

    def test_Install(self):
        """
        Install, pre-K/L version.
        """
        locator = self._patchManager.Locator()
        locator.url = MetaUrls[0]
        self.InvokeAndTrack(
            self._patchManager.Install,
            locator,
            VibUrls[0]
            )
        #task = self._patchManager.Install(locator, VibUrls[0])
        #self.failIfRaises(
        #    "Waiting for task expected not to raise.",
        #    vimutil.WaitForTask,
        #    task,
        #    pc=self._host.GetPropertyCollector()
        #    )
