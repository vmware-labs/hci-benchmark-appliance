#!/usr/bin/env python
"""
   These vmFeature tests know specifics of the library and how it is implemented.
   If the vmx format changes, these tests will need to be updated.
   See: https://wiki.eng.vmware.com/VMFeatureCompatTests for more information about vmFeature.

"""
from __future__ import print_function

import sys
import traceback
import re
import socket
import time

from pyVmomi import vim, vmodl
from pyVim import connect, task, arguments
from pyVim.vm import CreateQuickDummy, CreateQuickDummySpec
from pyVim.helpers import Log

excludeKeys = ['cpuid.Intel', 'cpuid.AMD', 'cpuid.Cyrix', 'cpuid.VIA']

levelMasks = [vim.host.FeatureMask(key='cpuid.NUMLEVELS',
                                   featureName='cpuid.NUMLEVELS',
                                   value='Val:1'),
              vim.host.FeatureMask(key='cpuid.NUM_EXT_LEVELS',
                                   featureName='cpuid.NUM_EXT_LEVELS',
                                   value='Val:0x80000008'),
             ]

def EVCMode(req, mask):
   return vim.EVCMode(featureRequirement=req,
                      featureMask=mask,
                      vendor="",
                      track=[''],
                      vendorTier=-1,
                     )

def Connect():
   return connect.SmartConnect(host=connectHost, user=user, pwd=pwd)

def Test0(si): # verify capabilities exist on the host
   success = 1
   cap = host.config.featureCapability
   if len(cap) == 0:
      Log("FeatureCapability not populated on host")
      success = 0

   if not success:
      raise Exception("Test0 failed")
   Log("Test0 PASSED")

def Test1(si): # verify masked value is set properly
   success = 1

   setTo = 0
   keyValue = GetFeatureCaps(host, count=2, val=setTo+1)
   mask = []
   for k,v in keyValue.items():
      mask.append(vim.host.FeatureMask(featureName=k, key=k, value="Max:%d" % setTo))

   evcTask = host.TestEvcMode(EVCMode(None,mask))
   task.WaitForTask(evcTask)
   testResult = evcTask.info.result
   if testResult and str(testResult).find("vim.HostSystem") == -1 and len(testResult.faults) > 0:
      Log("TestEvcMode of masks had VMs with exceptions")
      Log("%s" % testResult)
      success = 0

   task.WaitForTask(host.ApplyEvcMode(EVCMode(None, mask), False))
   if useVc:
      time.sleep(15) # any way to wait for host sync?
   maskedCaps = filter(lambda x: x.key in keyValue.keys(), host.config.maskedFeatureCapability)

   for cap in maskedCaps:
      if int(cap.value) != setTo:
         success = 0
         Log("Mask for %s is unexpected (Value: %s, Expected %s)" % (cap.key, cap.value, setTo))

   if not success:
      raise Exception("Test1 failed")
   Log("Test1 PASSED")

def Test2(si): # verify unsetting masks
   success = 1
   keyValue = {"cpuid.vendor": "Max:2",
               "cpuid.family": "Max:5"}

   evcTask = host.ApplyEvcMode(EVCMode(None, []), False)
   task.WaitForTask(evcTask)
   if useVc:
      time.sleep(15) # any way to wait for host sync?

   hostCaps = filter(lambda x: x.key in keyValue.keys(), host.config.featureCapability)
   maskedCaps = filter(lambda x: x.key in keyValue.keys(), host.config.maskedFeatureCapability)

   for maskCap in maskedCaps:
      for hostCap in hostCaps:
         if hostCap.key == maskCap.key and hostCap.value != maskCap.value:
            success = 0
            Log("Host Capability %s is still masked (Value: %s, Expected %s)" % (hostCap.key, maskCap.value, hostCap.value))

   if not success:
      raise Exception("Test2 failed")
   Log("Test2 PASSED")

def Test3(si): # Tests cap < req
   success = 1
   keyValue = {"cpuid.XSAVE": "Min",
               "cpuid.NX": "Match",}

   hostCaps = filter(lambda x: x.key in keyValue.keys(), host.config.featureCapability)
   req = []
   for cap in hostCaps:
      name = cap.featureName
      value = int(cap.value) + 1
      r = vim.vm.FeatureRequirement(key=name, featureName=name, value="%s:%s" % (keyValue[name], value))
      req.append(r)

   evcTask = host.TestEvcMode(EVCMode(req, None))
   try:
      task.WaitForTask(evcTask)
   except vim.fault.EVCAdmissionFailedCPUFeaturesForMode as e:
      result = e
   else:
      result = evcTask.info.result
      if 'faults' not in result.__dict__.keys():
         result=None
   if result is None or (len(result.faults[0].featureRequirement) != len(keyValue)):
      success = 0
      Log("No failed requirements set: %s" % result)

   if not success:
      raise Exception("Test3 failed")
   Log("Test3 PASSED")

def Test4(si): # Tests cap < req
   success = 1
   keyValue = {"cpuid.vendor": "Min",
               "cpuid.family": "Match"}

   hostCaps = filter(lambda x: x.key in keyValue.keys(), host.config.featureCapability)
   req = []
   for cap in hostCaps:
      name = cap.featureName
      value = cap.value
      r = vim.vm.FeatureRequirement(key=name, featureName=name, value="%s:%s" % (keyValue[name], value))
      req.append(r)

   evcTask = host.TestEvcMode(EVCMode(req, None))
   try:
      task.WaitForTask(evcTask)
   except vim.fault.EVCAdmissionFailedCPUFeaturesForMode as e:
      result = e
   else:
      result = evcTask.info.result
      if result and 'faults' not in result.__dict__.keys():
         result=None

   if result and len(result.faults) != 0:
      success = 0
      Log("Unexpected failed requirements set")
      print(result)

   if not success:
      raise Exception("Test4 failed")
   Log("Test4 PASSED")

def Test6(si):
   success = 1

   featureCapability = host.capability.featureCapabilitiesSupported

   if featureCapability != True:
      Log("FeatureCapability not supported on host")
      success = 0

   if not success:
      raise Exception("Test6 failed")
   Log("Test6 PASSED")

def Test7(si): # Tests cap < req
   success = 1
   ops = ["Min", "Match"]
   keyValue = GetFeatureCaps(host, count=2, val=0)
   Log("%s" % keyValue)
   hostCaps = filter(lambda x: x.key in keyValue.keys(), host.config.featureCapability)
   req = []
   for cap in hostCaps:
      name = cap.featureName
      value = 1 + int(cap.value)
      r = vim.vm.FeatureRequirement(key=name, featureName=name, value="%s:%s" % (ops[len(req)], value))
      req.append(r)

   applyTask = host.ApplyEvcMode(EVCMode(req, None), False)
   try:
      task.WaitForTask(applyTask)
   except Exception:
      Log("Exception thrown as expected")
   else:
      success = 0
      Log("%s" % req)
      Log("%s" % applyTask.info)
      Log("ApplyEvcMode succeeded even though req > cap")

   task.WaitForTask(host.ApplyEvcMode(EVCMode(None, None), False))

   if not success:
      raise Exception("Test7 failed")
   Log("Test7 PASSED")

"""
   configIssue test:
   Dummy VM must populate requirements after poweron.
   TestEvcMode should report the requirement issue if masks are lower than requirements
   ApplyEvcMode with ignoreVmEvcAdmissionFaults should cause the Dummy VM to have a configIssue

"""
def Test8(si, datastore, sim=False):
   success = 1

   vmName = "vmFeature-Test8"
   envBrowser = host.parent.environmentBrowser
   envBrowser = cluster.environmentBrowser
   resPool = cluster.resourcePool
   vmspec = CreateQuickDummySpec(vmName, 1, vmxVersion='vmx-09',
                                 datastoreName=datastore, envBrowser=envBrowser)
   vm = CreateVM(dc.vmFolder, vmspec, resPool, host)

   opts = []
   opts.append(vim.Option.OptionValue(key="featureCompat.enable", value="TRUE"))
   opts.append(vim.Option.OptionValue(key="answer.msg.checkpoint.resume.error", value="Preserve"))
   opts.append(vim.Option.OptionValue(key="answer.msg.checkpoint.resume.softError", value="Preserve"))
   spec = vim.Vm.ConfigSpec(extraConfig=opts)
   vmTask = vm.Reconfigure(spec)
   task.WaitForTask(vmTask, si=si)

   reqs = vm.runtime.featureRequirement
   if reqs is not None and len(reqs) > 0:
      Log("VM requirements populated unnecessarily")
      Log("%s" % reqs)
      success = 0

   filterobj = RetrieveFilterForRuntime(si, vm)
   updates = si.content.propertyCollector.WaitForUpdatesEx(None,
      vmodl.Query.PropertyCollector.WaitOptions(maxWaitSeconds=20))
   version = updates.version

   task.WaitForTask(vm.PowerOn())

   updates = si.content.propertyCollector.WaitForUpdatesEx(version,
      vmodl.Query.PropertyCollector.WaitOptions(maxWaitSeconds=20))

   if updates is None:
      Log("No updates for featureRequirements/featureMasks after poweron")
      success = 0
   else:
      version = updates.version

   reqs = vm.runtime.featureRequirement

   if reqs is None or len(reqs) == 0:
      Log("VM requirements not populated")
      success = 0

   keyValue = GetFeatureReqs(reqs, 1, 1)
   for k,v in keyValue.items():
      keyValue[k]['operation'] = "Max"
      keyValue[k]['value'] = int(v['value']) - 1

   mask = []
   for k,v in keyValue.items():
      mask.append(vim.host.FeatureMask(featureName=k, key=k,
                                       value="%s:%d" % (v['operation'], v['value'])))
   Log("%s" % mask)
   evcTask = host.TestEvcMode(EVCMode(None, mask))
   try:
      task.WaitForTask(evcTask)
   except (vim.fault.EVCAdmissionFailedCPUFeaturesForMode,
           vim.fault.EVCAdmissionFailedVmActive) as e:
      result = e
   else:
      result = evcTask.info.result
      if 'faults' not in result.__dict__.keys():
         result=None

   if result is None or len(result.faults) == 0:
      Log("TestEvcMode did not populate req for '%s'" % ''.join(keyValue.keys()))
      success = 0

   task.WaitForTask(ApplyEvcMode(host, EVCMode(None, mask), True))

   if len(vm.configIssue) == 0:
      success = 0
      Log("No ConfigIssues raised for VM %s" % vm.name)

   task.WaitForTask(vm.Suspend())

   try:
      task.WaitForTask(vm.PowerOn())
   except Exception as e:
      if vm.runtime.question is not None:
         Log("Questions for VM: %s" % vm.runtime.question)
         success = 0
      Log("Exception %s raised as expected" % e)
   else:
      time.sleep(5)
      if len(vm.configIssue) > 0:
         Log("ConfigIssue raised, but expected PowerOn failure")
         if sim == False:
            success = 0
      else:
         Log("No config issue, PowerOn was allowed by vmx")
         success = 0
         Log("Previous reqs were %s" % reqs)
         Log("Current reqs are %s" % vm.runtime.featureRequirement)

   time.sleep(5) # XXX: shouldn't be necessary
   task.WaitForTask(vm.PowerOff())

   updates = si.content.propertyCollector.WaitForUpdatesEx(version,
      vmodl.Query.PropertyCollector.WaitOptions(maxWaitSeconds=20))

   if updates is not None:
      version = updates.version

   if len(vm.configIssue) > 0:
      success = 0
      Log("VM ConfigIssues remaining after power off")
      if len(vm.runtime.featureRequirement) > 0:
         Log("%s" % vm.runtime.featureRequirement)
      Log("%s" % vm.configIssue)

   filterobj.Destroy()
   try:
      task.WaitForTask(vm.PowerOff())
   except: pass
#   task.WaitForTask(vm.Destroy())

   task.WaitForTask(host.ApplyEvcMode(EVCMode(None, None), True))

   if not success:
      raise Exception("Test8 failed")
   Log("Test8 PASSED")

def Test5(si, datastore, sim=False):
   success = 1

   vmName = "vmFeature-Test5"
   envBrowser = host.parent.environmentBrowser
   envBrowser = cluster.environmentBrowser
   resPool = cluster.resourcePool
   vmspec = CreateQuickDummySpec(vmName, 1, vmxVersion='vmx-09',
                                 datastoreName=datastore, envBrowser=envBrowser)
   vm = CreateVM(dc.vmFolder, vmspec, resPool, host)

   opt = vim.Option.OptionValue(key="featureCompat.enable", value="TRUE")
   spec = vim.Vm.ConfigSpec(extraConfig=[opt])
   vmTask = vm.Reconfigure(spec)
   task.WaitForTask(vmTask, si=si)

   for i in range(3):
      vmTask = vm.PowerOn()
      while vmTask.info.progress != 100 and vmTask.info.state not in ['success', 'error']:
         # fetch runtime while poweron to exercise potential race in vigor
         # populating featureRequirement/featureMask
         runtime = vm.runtime
      task.WaitForTask(vmTask)
      task.WaitForTask(vm.PowerOff())

   task.WaitForTask(vm.Destroy())
   if not success:
      raise Exception("Test5 failed")
   Log("Test5 PASSED")

def Test9(si): # mockup upscale
   success = 1
   ops = ["Min", "Match"]

   setTo = 1
   keyValue = GetFeatureCaps(host, count=2, val=setTo-1)
   mask = []
   for k,v in keyValue.items():
      mask.append(vim.host.FeatureMask(featureName=k, key=k, value="Min:%d" % setTo))

   try:
      task.WaitForTask(ApplyMockupFeatures(host, mask))
   except Exception as e:
      Log("%s" % mask)
      raise

   hostCaps = filter(lambda x: x.key in keyValue.keys(), host.config.featureCapability)
   for cap in hostCaps:
      name = cap.featureName
      value = cap.value
      if int(value) != int(setTo):
         success = 0
         Log("Feature %s was expected to be %d, but was %d" % (name, int(setTo), int(value)))

   task.WaitForTask(host.ApplyMockupFeatures([]))

   hostCaps = filter(lambda x: x.key in keyValue.keys(), host.config.featureCapability)
   for cap in hostCaps:
      name = cap.featureName
      value = cap.value
      if int(value) != int(setTo-1):
         success = 0
         Log("Feature %s was not reverted to %d correctly, was %d" % (name, int(setTo -1), int(value)))

   if not success:
      raise Exception("Test9 failed")
   Log("Test9 PASSED")

def Test10(si): # mask down & mockup upscale
   success = 1
   ops = ["Min", "Match"]

   maskSetTo = 0
   keyValue = GetFeatureCaps(host, count=1, val=maskSetTo+1)
   mask = []
   for k,v in keyValue.items():
      mask.append(vim.host.FeatureMask(featureName=k, key=k, value="Max:%d" % maskSetTo))

   task.WaitForTask(host.ApplyEvcMode(EVCMode(None, mask), True))

   hostMaskedCaps = filter(lambda x: x.key in keyValue.keys(), host.config.maskedFeatureCapability)
   for cap in hostMaskedCaps:
      name = cap.featureName
      value = cap.value
      if int(value) != int(maskSetTo):
         Log("Feature %s was expected to be %d, but was %d" % (name, int(maskSetTo), int(value)))

   setTo = 1
   for entry in mask:
      entry.value="Min:%d" % setTo

   task.WaitForTask(ApplyMockupFeatures(host, mask))

   hostMaskedCaps = filter(lambda x: x.key in keyValue.keys(), host.config.maskedFeatureCapability)
   for cap in hostMaskedCaps:
      name = cap.featureName
      value = cap.value
      if int(value) != int(maskSetTo):
         success = 0
         Log("Feature %s was expected to be %d, but was %d" % (name, int(maskSetTo), int(value)))

   task.WaitForTask(host.ApplyMockupFeatures([]))
   task.WaitForTask(host.ApplyEvcMode(EVCMode(None, None), True))

   if not success:
      raise Exception("Test10 failed")
   Log("Test10 PASSED")

def Test11(si, datastore, sim=False):
   success = 1

   vmName = "vmFeature-Test11"
   envBrowser = host.parent.environmentBrowser
   envBrowser = cluster.environmentBrowser
   resPool = cluster.resourcePool

   vmspec = CreateQuickDummySpec(vmName, 1, vmxVersion='vmx-09',
                                 guest="rhel5_64Guest",
                                 datastoreName=datastore, envBrowser=envBrowser,
                                 ctlrType="lsilogic")
   vm = CreateVM(dc.vmFolder, vmspec, resPool, host)

   opt = vim.Option.OptionValue(key="featureCompat.enable", value="TRUE")
   spec = vim.Vm.ConfigSpec(extraConfig=[opt])
   task.WaitForTask(vm.Reconfigure(spec), si=si)

   reqs = vm.runtime.featureRequirement
   offlineReqs = vm.runtime.offlineFeatureRequirement
   if offlineReqs is None or len(offlineReqs) == 0:
      success = 0
      Log("Requirements not populated for 64-bit guest")

   task.WaitForTask(vm.Reconfigure(vim.Vm.ConfigSpec(guestId="winNetEnterpriseGuest")))

   offlineReqs = vm.runtime.offlineFeatureRequirement
   if offlineReqs is not None and len(offlineReqs) > 0:
      success = 0
      Log("%s" % offlineReqs)
      Log("Requirements populated for 32-bit guest")

   task.WaitForTask(vm.Destroy())
   if not success:
      raise Exception("Test11 failed")
   Log("Test11 PASSED")

def Test12(si): # verify masks and reqs exceeding cap generate fault
   success = 1

   setTo = 1
   keyValue = GetFeatureCaps(host, count=2, val=setTo-1)
   mask = []
   req = []
   for k,v in keyValue.items():
      mask.append(vim.host.FeatureMask(featureName=k, key=k, value="Val:%d" % setTo))
      req.append(vim.vm.FeatureRequirement(featureName=k, key=k, value="Min:%d" % setTo))

   evcTask = host.TestEvcMode(EVCMode(req, mask))
   try:
      task.WaitForTask(evcTask)
   except vim.fault.EVCAdmissionFailedCPUFeaturesForMode as e:
      testResult = e
   else:
      testResult = evcTask.info.result
      if 'faults' not in testResult.__dict__.keys():
         testResult=None

   if testResult is None or len(testResult.faults) == 0:
      Log("TestEvcMode of masks and req exceeding cap had no exception")
      success = 0

   if not success:
      raise Exception("Test12 failed")
   Log("Test12 PASSED")

def Test13(si): # if intel, do a real evc mode test
   success = 1
   isIntel = 0
   for cap in host.config.featureCapability:
      if cap.key == "cpuid.Intel" and cap.value == "1":
         isIntel = 1
         break

   if isIntel == 0:
      Log("Test13 Host is not Intel, skipping test")
      return

   featureMap = {
      'cpuid.STEPPING':'Val:0xa',
      'cpuid.Intel':'Val:1',
      'cpuid.MODEL':'Val:0x17',
      'cpuid.XSAVE':'Val:1',
      'cpuid.LM':'Val:1',
      'cpuid.NUM_EXT_LEVELS':'Val:0x80000008',
      'cpuid.MWAIT':'Val:1',
      'cpuid.FAMILY':'Val:6',
      'cpuid.SSSE3':'Val:1',
      'cpuid.SSE3':'Val:1',
      'cpuid.NX':'Val:1',
      'cpuid.SSE41':'Val:1',
      'cpuid.SS':'Val:1',
      'cpuid.DS':'Val:1',
      'cpuid.LAHF64':'Val:1',
      'cpuid.CMPXCHG16B':'Val:1',
      'cpuid.NUMLEVELS':'Val:0xd',
      'cpuid.VMX':'Val:1',
                }
   mockups = []
   for k,v in featureMap.items():
      mockups.append(vim.host.FeatureMask(key=k, featureName=k, value=v))
   task.WaitForTask(host.ApplyMockupFeatures(mockups))

   # now testEvcMode

   evcReqMap = {
      'cpuid.Intel':'Bool:Min:1',
      'cpuid.XSAVE':'Bool:Min:1',
      'cpuid.LM':'Bool:Min:1',
      'cpuid.MWAIT':'Bool:Min:1',
      'cpuid.SSSE3':'Bool:Min:1',
      'cpuid.SSE3':'Bool:Min:1',
      'cpuid.NX':'Bool:Min:1',
      'cpuid.SSE41':'Bool:Min:1',
      'cpuid.SS':'Bool:Min:1',
      'cpuid.DS':'Bool:Min:1',
      'cpuid.LAHF64':'Bool:Min:1',
      'cpuid.CMPXCHG16B':'Bool:Min:1',
            }
   evcMaskMap = {
      'cpuid.STEPPING':'Val:1',
      'cpuid.Intel':'Val:1',
      'cpuid.MODEL':'Val:0xf',
      'cpuid.XSAVE':'Val:1',
      'cpuid.LM':'Val:1',
      'cpuid.NUM_EXT_LEVELS':'Val:0x80000008',
      'cpuid.MWAIT':'Val:1',
      'cpuid.FAMILY':'Val:6',
      'cpuid.SSSE3':'Val:1',
      'cpuid.SSE3':'Val:1',
      'cpuid.NX':'Val:1',
      'cpuid.SSE41':'Val:1',
      'cpuid.SS':'Val:1',
      'cpuid.DS':'Val:1',
      'cpuid.LAHF64':'Val:1',
      'cpuid.CMPXCHG16B':'Val:1',
      'cpuid.NUMLEVELS':'Val:0xa',
                }
   evcReqs = []
   evcMasks = []

   for k,v in evcReqMap.items():
      evcReqs.append(vim.vm.FeatureRequirement(key=k, featureName=k, value=v))
   for k,v in evcMaskMap.items():
      evcMasks.append(vim.host.FeatureMask(key=k, featureName=k, value=v))

   evcTask = host.TestEvcMode(EVCMode(evcReqs, evcMasks))
   task.WaitForTask(evcTask)
   Log("%s" % evcTask.info.result)

   task.WaitForTask(host.ApplyMockupFeatures([]))

   if not success:
      raise Exception("Test13 failed")
   Log("Test13 PASSED")

def Test14(si, datastore, sim=False):
   success = 1

   vmName = "vmFeature-Test14"
   envBrowser = host.parent.environmentBrowser
   envBrowser = cluster.environmentBrowser
   resPool = cluster.resourcePool

   vmspec = CreateQuickDummySpec(vmName, 1, vmxVersion='vmx-09',
                                 guest="rhel5_64Guest",
                                 datastoreName=datastore, envBrowser=envBrowser,
                                 ctlrType="lsilogic")
   vm = CreateVM(dc.vmFolder, vmspec, resPool, host)

   opt = vim.Option.OptionValue(key="featureCompat.enable", value="TRUE")
   spec = vim.Vm.ConfigSpec(extraConfig=[opt])
   task.WaitForTask(vm.Reconfigure(spec), si=si)

   offlineReqs = vm.runtime.offlineFeatureRequirement
   if offlineReqs is None or len(offlineReqs) == 0:
      success = 0
      Log("Requirements not populated for 64-bit guest")

   task.WaitForTask(vm.PowerOn())
   reqs = vm.runtime.featureRequirement
   if len(reqs) <= len(offlineReqs):
      success = 0
      Log("Number of requirements did not exceed expected")
      Log("%s" % reqs)
   task.WaitForTask(vm.PowerOff())

   path = vm.config.files.vmPathName
   vm.Unregister()
   vmRegTask = dc.vmFolder.RegisterVm(path, asTemplate=False, pool=resPool, host=host)
   task.WaitForTask(vmRegTask)
   vm = vmRegTask.info.result

   offlineReqs = vm.runtime.offlineFeatureRequirement
   if offlineReqs is None or len(offlineReqs) == 0:
      success = 0
      Log("Requirements not populated after register")

   task.WaitForTask(vm.Destroy())
   if not success:
      raise Exception("Test14 failed")
   Log("Test14 PASSED")

def Test15(si, datastore, sim=False):
   success = 1

   vmName = "vmFeature-Test15"
   envBrowser = host.parent.environmentBrowser
   envBrowser = cluster.environmentBrowser
   resPool = cluster.resourcePool

   vmspec = CreateQuickDummySpec(vmName, 1, vmxVersion='vmx-09',
                                 guest="rhel5_64Guest",
                                 datastoreName=datastore, envBrowser=envBrowser,
                                 ctlrType="lsilogic")
   vm = CreateVM(dc.vmFolder, vmspec, resPool, host)

   opts = []
   opts.append(vim.Option.OptionValue(key="featureCompat.enable", value="TRUE"))
   opts.append(vim.Option.OptionValue(key="answer.msg.cpuid.noVHVQuestion", value="No"))
   spec = vim.Vm.ConfigSpec(extraConfig=opts)
   spec.nestedHVEnabled = True
   task.WaitForTask(vm.Reconfigure(spec), si=si)

   offlineReqs = vm.runtime.offlineFeatureRequirement
   if offlineReqs is None or len(offlineReqs) < 2:
      success = 0
      Log("%s" % offlineReqs)
      Log("Requirements not populated for 64-bit guest and nestedHV")

   featureHide = ['cpuid.VMX', 'cpuid.SVM']
   # disable hv.capable
   mask = []
   for feature in featureHide:
      mask.append(vim.host.FeatureMask(featureName=feature, key=feature, value='Max:0'))

   task.WaitForTask(ApplyMockupFeatures(host, mask))

   try:
      task.WaitForTask(vm.PowerOn())
   except Exception as e:
      Log("Hit exception as expected: %s" % e)
   else:
      success = 0
      Log("Power on succeeded even though hv is false")

   spec = vim.Vm.ConfigSpec()
   spec.nestedHVEnabled = False
   task.WaitForTask(vm.Reconfigure(spec), si=si)

   offlineReqs = vm.runtime.offlineFeatureRequirement
   if offlineReqs is None or len(offlineReqs) >= 2:
      success = 0
      Log("%s" % offlineReqs)
      Log("More requirements than expected")

   if vm.runtime.powerState != "poweredOff":
      try:
         task.WaitForTask(vm.PowerOff())
      except: pass

   task.WaitForTask(vm.Destroy())

   task.WaitForTask(host.ApplyMockupFeatures([]))

   if not success:
      raise Exception("Test15 failed")
   Log("Test15 PASSED")

def Test16(si): # mockup upscale failure
   success = 1
   ops = ["Min", "Match"]
   matchVal = 1
   keyValue = GetFeatureCaps(host, count=1, val=matchVal)

   setTo = 1
   mask = []
   key = "MSR.0x480"
   mask.append(vim.host.FeatureMask(featureName=key, key=key,
                                    value="Val:0xda08000000000d"))

   try:
      task.WaitForTask(ApplyMockupFeatures(host, mask))
   except Exception as e:
      Log("ApplyMockupFeatures failed as expected: %s" % e)
      hostCaps = filter(lambda x: x.key in keyValue.keys(), host.config.featureCapability)
      if len(hostCaps) == 0 or int(hostCaps[0].value) != matchVal:
         Log("Caps not preserved as expected")
         success = 0
   else:
      Log("Expected failure, but none thrown")
      success = 0

   task.WaitForTask(host.ApplyMockupFeatures([]))

   if not success:
      raise Exception("Test16 failed")
   Log("Test16 PASSED")


def RetrieveFilterForRuntime(si, vm):
   sc = si.RetrieveContent()
   pc = sc.GetPropertyCollector()
   propSpec = vmodl.query.PropertyCollector.PropertySpec(type=vim.VirtualMachine, all=False, pathSet=["runtime.featureMask", "runtime.featureRequirement"])
   objSpec = vmodl.Query.PropertyCollector.ObjectSpec(obj=vm, skip=False)

   # Create a filter spec with the specified object and property spec.
   filterspec = vmodl.Query.PropertyCollector.FilterSpec(propSet=[propSpec], objectSet=[objSpec])

   # Create the filter
   return pc.CreateFilter(filterspec, True)

def CreateVM(vmFolder, config, resPool, host):
   createTask = vmFolder.CreateVm(config, resPool, host)
   task.WaitForTask(createTask)
   return createTask.info.result

def GetHostByName(si, hostname):
   for entry in GetHostList(si.content.rootFolder):
      # sometimes the user doesn't put the hostname in correctly
      # and the lookup fails. Not all cases can be addressed, but
      # try striping everything after the '.' and see if we get
      # a valid name.
      splithost = entry['host'].name.split(".")[0]
      if entry['host'].name == hostname or \
         LookupHost(entry['host'].name) == LookupHost(hostname) or \
         LookupHost(splithost) == LookupHost(hostname):

         global host
         global dc
         global cluster
         host = entry['host']
         dc = entry['dc']
         cluster = entry['cluster']

         return host
   return None

def LookupHost(hostname):
   try:
      addr = socket.getaddrinfo(hostname, None)
   except:
      return None
   return addr[1][4][0]

def GetHostList(folder, dc=None, cluster=None):
   hostList = []
   for file in folder.childEntity:
      fileType = "%s" % file
      if fileType.find('vim.Folder') != -1:
         hostList += GetHostList(file, dc, cluster)
      elif fileType.find('vim.Datacenter') != -1:
         hostList += GetHostList(file.hostFolder, file, cluster)
      elif fileType.find('vim.ClusterComputeResource') != -1:
         hostList += [{'host':file.host, 'dc':dc, 'cluster':cluster}]
      elif fileType.find('vim.ComputeResource') != -1:
         for host in file.host:
            hostList += [{'host':host, 'dc':dc, 'cluster':file}]
   return hostList

def GetFeatureCaps(host, count=1, val=1):
   keyValues = {}

   for cap in host.config.featureCapability:
      if cap.key in excludeKeys:
         continue
      if int(cap.value) == int(val):
         keyValues[cap.key] = cap.value
      if len(keyValues) == count:
         break
   return keyValues

def GetFeatureReqs(reqs, count=1, val=1):
   keyValues = {}

   for op in reqs:
      if len(keyValues) >= count:
         break
      if op.key in excludeKeys:
         continue
      m = re.match("(?P<type>)?:?(?P<operation>.*):(?P<value>.*)", op.value)
      if m:
         operation = m.group('operation')
         value = m.group('value')
         if int(value) == val:
            keyValues[op.key] = {"operation":operation, "value":value}
            Log("Mask %s=%s" % (op.key, keyValues[op.key]))
            continue
   return keyValues

# An implementation for incompleteMasks=True
def ApplyMockupFeatures(host, mask):
   maskKeys = map(lambda x: x.key, mask)

   for cap in host.config.featureCapability:
      if cap.key not in maskKeys:
         mask.append(vim.host.FeatureMask(featureName=cap.key, key=cap.key, value="Min:%s" % cap.value))

   mask += levelMasks

   return host.ApplyMockupFeatures(mask)

def ApplyEvcMode(host, evcMode, ignoreVmEvcAdmissionFaults):
   maskKeys = map(lambda x: x.key, evcMode.featureMask)

   for cap in host.config.featureCapability:
      if cap.key not in maskKeys:
         evcMode.featureMask.append(vim.host.FeatureMask(featureName=cap.key, key=cap.key, value="Val:%s" % cap.value))

   evcMode.featureMask += levelMasks

   return host.ApplyEvcMode(evcMode, ignoreVmEvcAdmissionFaults)

def main():
   status = "PASS"

   supportedArgs = [ (["H:", "primary host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "", "Password", "pwd"),
                     (["v:", "vc="], "", "VC Server", "vc"),
                     (["d:", "datastore="], None, "Datastore", "datastore"), ]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage"),
                        (["sim"], False, "Host simulator", "sim"), ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(1)

   # Process command line
   global user
   global pwd
   user=args.GetKeyValue("user")
   pwd=args.GetKeyValue("pwd")

   hostname = args.GetKeyValue("host")
   vc = args.GetKeyValue("vc")
   datastore = args.GetKeyValue("datastore")
   si = None
   global useVc
   if vc:
      useVc = True
   else:
      useVc = False
   global connectHost
   connectHost = vc if useVc else hostname

   try:
      # Connect to host
      si = Connect()
      if si is None:
         raise Exception("Failed to connect to %s" % connectHost)
      Log("Connected to %s" % connectHost)
      if useVc:
         configs = []
         configs.append(vim.option.OptionValue(key='config.featureCompat.enable', value='true'))
         configs.append(vim.option.OptionValue(key='config.featureCompat.enableHWv9', value='true'))
         si.content.setting.UpdateValues(configs)

      GetHostByName(si, hostname)
      Test0(si)
      Test1(si)
      Test2(si)
      Test3(si)
      Test4(si)
      Test5(si, datastore)
      Test6(si)
      Test7(si)
      Test8(si, datastore, args.GetKeyValue("sim"))
      Test9(si)
      Test10(si)
      Test11(si, datastore, args.GetKeyValue("sim"))
      Test12(si)
      Test13(si)
      Test14(si, datastore, args.GetKeyValue("sim"))
      Test15(si, datastore, args.GetKeyValue("sim"))
      Test16(si)
      Log("ALL TESTS PASSED")
   except Exception as e:
      Log("Caught exception : " + str(e))
      traceback.print_exc()
      status = "FAIL"
   finally:
      if si:
         connect.Disconnect(si)
   if status == "FAIL":
      sys.exit(1)

# Start program
if __name__ == "__main__":
    main()

