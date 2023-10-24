#!/usr/bin/python

import argparse
import atexit
import codecs
import errno
import os
import re
import shutil
import sys
import time
import traceback
from pyVmomi import Vim, Vmodl
from pyVim import folder, host, invt, path, vimutil, vm, vmconfig
from pyVim.connect import SmartConnect, Disconnect, GetSi
from pyVim.helpers import Log, StopWatch
from pyVim.task import WaitForTask

VM_NAME_PREFIX = os.environ.get('TESTESX_PREFIX', 'VmxSandboxTestVM')

class Phase:
   def __init__(self):
      self.phaseNumber = 0
      self.phaseClock = StopWatch()

   def SetPhase(self, msg):
      Log("Phase " + str(self.phaseNumber) + ": " + msg + " completed")
      self.phaseClock.finish("phase " + str(self.phaseNumber))
      self.phaseClock = StopWatch()
      self.phaseNumber = self.phaseNumber + 1

def ResolveDsPath(vm1, dsPath, symbolicName=False):
   match = re.search(r'\[(.+)\]\s*(\S+)', dsPath)
   ds = match.group(1)
   relPath = match.group(2)
   if symbolicName:
      return os.path.join('/vmfs/volumes', ds, relPath)
   fullPath = ''
   for d in vm1.GetDatastore():
      if d.GetName() == ds:
         fullPath = os.path.join(d.GetInfo().GetUrl(), relPath)
         break
   if not fullPath:
      raise Exception('Cannot resolve path for datastore %s' % ds)
   return fullPath

def GetVMHomeDir(vm1):
   return os.path.dirname(
             ResolveDsPath(vm1, vm1.GetSummary().GetConfig().GetVmPathName()))

def FindDomain(domainName):
   global vsi
   domID = None
   for domain in sorted(vsi.list('/vmkAccess/domains'), key=int):
      domPath = '/vmkAccess/domains/' + domain
      domainInfo = vsi.get(domPath + '/domainInfo')
      if domainInfo['name'] == domainName:
         domID = domain
   return domID

def RetrieveFilePolicy(domainName):
   global vsi
   domID = FindDomain(domainName)
   filePolicy = {}
   if domID:
      filePolicies = '/vmkAccess/domains/' + domID + '/filePathPolicies/'
      for policy in vsi.list(filePolicies):
         entry = vsi.get(filePolicies + policy + '/filePathPolicyInfo')
         filePolicy[entry['filePath']] = entry['permissions']
   return filePolicy

def CheckInPolicy(domainName, rules, exactMatch=False):
   found = []
   policy = RetrieveFilePolicy(domainName)
   for path, perm in rules:
      while not exactMatch:
         if path in policy and policy[path] & perm == perm:
            found += [path]
            break
         tail = path.rfind('/')
         if tail == -1:
            break
         path = path[0:tail]
   return found

def DumpFilePolicy(domainName):
   policy = RetrieveFilePolicy(domainName)
   Log('Retrieved %u rules for domain %s' % (len(policy), domainName))
   for path, perm in policy.items():
      Log('  filePath: ' + path + '\tpermission: ' + str(perm))

def AddCdromISO(vm1, isoFile):
   cspec = Vim.Vm.ConfigSpec()
   cspec = vmconfig.AddSataCtlr(cspec)
   vmconfig.AddSataCdrom(cspec, isoFilePath='[] ' + isoFile)
   vm.Reconfigure(vm1, cspec)
   cdromDevs = vmconfig.CheckDevice(vm1.GetConfig(),
                                    Vim.Vm.Device.VirtualCdrom)
   if len(cdromDevs) != 1:
      raise Exception('Failed to add cdrom device')
   ctlrs = vmconfig.CheckDevice(vm1.config, Vim.Vm.Device.VirtualSATAController)
   assert(len(ctlrs) == 1)
   return cdromDevs[0], ctlrs[0]

def AddEditSerialSymlinkFile(vm1, pathBase, serialDev = None):
   serialFilePath = pathBase + '-serial/serial.log'
   serialFullPath = ResolveDsPath(vm1, serialFilePath)
   serialSymlink = ResolveDsPath(vm1, pathBase + '/serial.log')
   os.symlink(serialFullPath, serialSymlink)
   cspec = Vim.Vm.ConfigSpec()
   if serialDev:
      backing = Vim.Vm.Device.VirtualSerialPort.FileBackingInfo()
      backing.SetFileName(serialFilePath)
      serialDev.SetBacking(backing)
      vmconfig.AddDeviceToSpec(cspec, serialDev,
                               Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
   else:
      vmconfig.AddFileBackedSerial(cspec, serialFilePath)
   vm.Reconfigure(vm1, cspec)
   devices = vmconfig.CheckDevice(vm1.GetConfig(),
                                  Vim.Vm.Device.VirtualSerialPort)
   if len(devices) != 1:
      raise Exception('Failed to add serial port')
   return devices[0], serialFullPath, serialSymlink

def AddSerialPipeBacked(vm1):
   extraCfg = [Vim.Option.OptionValue(
                  key='answer.msg.noAutodetectBackingQuestion', value='Yes')]
   cspec = Vim.Vm.ConfigSpec(extraConfig=extraCfg)
   cspec = vmconfig.AddPipeBackedSerial(cspec, pipeName='foo')
   vm.Reconfigure(vm1, cspec)
   devices = vmconfig.CheckDevice(vm1.GetConfig(),
                                  Vim.Vm.Device.VirtualSerialPort)
   if len(devices) != 1:
      raise Exception('Failed to add serial port')
   return devices[0]

def CreateDirectory(directory):
   fileManager = GetSi().RetrieveContent().GetFileManager()
   try:
      fileManager.MakeDirectory(directory)
   except Vim.fault.FileAlreadyExists:
      pass

def AddSuspendDirectory(vm1, pathBase):
   suspendDir = pathBase + '-suspend'
   CreateDirectory(suspendDir)
   files = Vim.Vm.FileInfo()
   files.SetSuspendDirectory(suspendDir)
   cspec = Vim.Vm.ConfigSpec()
   cspec.SetFiles(files)
   vm.Reconfigure(vm1, cspec)
   suspendDirPath = vm1.GetConfig().GetFiles().GetSuspendDirectory()
   if suspendDirPath != suspendDir:
      raise Exception('Failed to set suspend directory')
   return suspendDir

def AddDiskExternalDir(vm1, pathBase, datastore):
   diskDir = pathBase + '-disk'
   CreateDirectory(diskDir)
   cspec = Vim.Vm.ConfigSpec()
   diskRelPath = re.sub(r'\[.*\]\s*', '', diskDir) + '/testDisk.vmdk'
   cspec = vmconfig.AddScsiCtlr(cspec)
   vmconfig.AddScsiDisk(cspec, datastorename=datastore, fileName=diskRelPath,
                        thin=True, createNamedFile=True)
   vm.Reconfigure(vm1, cspec)
   devices = vmconfig.CheckDevice(vm1.GetConfig(), Vim.Vm.Device.VirtualDisk)
   if len(devices) < 2:
      raise Exception('Failed to find added disk')
   return devices[1], diskDir

def TestInitialFilePolicy(vm1, datastore=None):
   # Basic dummy VM should at least have permission for its home directory
   domainName = 'hostd' + str(vm1._GetMoId())
   vm.PowerOn(vm1)
   vmxPath = vm1.GetSummary().GetConfig().GetVmPathName()
   vmdir = os.path.dirname(ResolveDsPath(vm1, vmxPath))
   found = CheckInPolicy(domainName, [(vmdir, 3)])
   if len(found) != 1:
      DumpFilePolicy(domainName)
      raise Exception('Did not find VM home directory policy after power-on')

   vm.PowerOff(vm1)
   if FindDomain(domainName):
      raise Exception('Domain %s has not been cleaned up' % domainName)

   Log('Test setting nvram_default in global config')
   globalConf = '/etc/vmware/config'
   nvramPath = '/vmfs/volumes/testVol1/non_existent_nvram'
   shutil.copy2(globalConf, globalConf + '.backup')
   with open(globalConf, 'a') as f:
      f.write('nvram_default = "' + nvramPath + '"' + '\n')
   vm.PowerOn(vm1)
   shutil.move(globalConf + '.backup', globalConf)
   found = CheckInPolicy(domainName, [(nvramPath, 1)])
   if len(found) != 1:
      DumpFilePolicy(domainName)
      raise Exception('Did not find permission for nvram_default path')
   vm.PowerOff(vm1)

   toolsIso = '/vmimages/tools-isoimages/linux.iso'
   if os.path.isfile(toolsIso):
      Log('Test CDROM image config option')
      cdromDev, ctlr = AddCdromISO(vm1, toolsIso)
      vm.PowerOn(vm1)
      toolsIsoRP = os.path.realpath(toolsIso)
      found = CheckInPolicy(domainName, [(toolsIsoRP, 1)])
      if len(found) != 1:
         DumpFilePolicy(domainName)
         raise Exception('Did not find cdrom image permission')
      vm.PowerOff(vm1)
      # Remove cdrom device
      cspec = Vim.Vm.ConfigSpec()
      vmconfig.RemoveDeviceFromSpec(cspec, cdromDev)
      vmconfig.RemoveDeviceFromSpec(cspec, ctlr)
      vm.Reconfigure(vm1, cspec)

   Log('Test symlink serial backing file')
   pathBase = os.path.dirname(vmxPath)
   serialDev, fullPath, symlink = AddEditSerialSymlinkFile(vm1, pathBase)
   vm.PowerOn(vm1)
   found = CheckInPolicy(domainName, [(fullPath, 3)])
   if len(found) != 1:
      DumpFilePolicy(domainName)
      raise Exception('Did not find serial log permission')
   vm.PowerOff(vm1)
   # Remove serial device
   cspec = Vim.Vm.ConfigSpec()
   vmconfig.RemoveDeviceFromSpec(cspec, serialDev)
   vm.Reconfigure(vm1, cspec)
   os.unlink(symlink)

   Log('Test log file path with environment variables')
   logDir = pathBase + '-root'
   CreateDirectory(logDir)
   logDirPath = ResolveDsPath(vm1, logDir)
   logFullPath = re.sub(r'-root', '-$USER', logDirPath) + 'vmx-$PID.log'
   vmxLogOpt = Vim.Option.OptionValue(key='vmx.fileTrack.logFile',
                                      value=logFullPath)
   cspec = Vim.Vm.ConfigSpec(extraConfig=[vmxLogOpt])
   vm.Reconfigure(vm1, cspec)
   vm.PowerOn(vm1)
   found = CheckInPolicy(domainName, [(logDirPath, 3)])
   if len(found) != 1:
      DumpFilePolicy(domainName)
      raise Exception('Did not find log file permission')
   vm.PowerOff(vm1)
   vmxLogOpt = Vim.Option.OptionValue(key='vmx.fileTrack.logFile', value='')
   cspec = Vim.Vm.ConfigSpec(extraConfig=[vmxLogOpt])
   vm.Reconfigure(vm1, cspec)
   fileManager = GetSi().RetrieveContent().GetFileManager()
   vimutil.InvokeAndTrack(fileManager.Delete, datastorePath=logDir,
                          fileType=Vim.FileManager.FileType.File)

   Log('Test setting workingDir')
   workingDir = pathBase + '-workingDir'
   workingDirFullPath = ResolveDsPath(vm1, workingDir)
   workingDirSymPath = ResolveDsPath(vm1, workingDir, True)
   CreateDirectory(workingDir)
   vmxFullPath = ResolveDsPath(vm1, vmxPath)
   shutil.copy2(vmxFullPath, vmxFullPath + '.backup')
   vmxOut = codecs.open(vmxFullPath, mode='w+', encoding='utf_8')
   with codecs.open(vmxFullPath + '.backup', encoding='utf_8') as vmxIn:
      for line in vmxIn:
         if 'migrate.hostlog' not in line:
            vmxOut.write(line)
   vmxOut.write('workingDir = "%s"\n' % workingDirSymPath)
   vmxOut.close()
   vm.PowerOn(vm1)
   found = CheckInPolicy(domainName, [(workingDirFullPath, 3)])
   filesFound = os.listdir(workingDirFullPath)
   if len(filesFound) == 0:
      raise Exception('No files found in working directory %s' %
                      workingDirFullPath)
   vm.PowerOff(vm1)
   # Power cycle to verify VM is still in a valid state
   vm.PowerOn(vm1)
   vm.PowerOff(vm1)
   shutil.move(vmxFullPath + '.backup', vmxFullPath)
   fileManager = GetSi().RetrieveContent().GetFileManager()
   vimutil.InvokeAndTrack(fileManager.Delete, datastorePath=workingDir,
                          fileType=Vim.FileManager.FileType.File)
   vm.PowerOn(vm1)
   vm.PowerOff(vm1)

   # Create suspend directory, additional disk directory
   Log('Test setting suspend directory and adding a new disk')
   suspendDir = AddSuspendDirectory(vm1, pathBase)
   diskDev, diskDir = AddDiskExternalDir(vm1, pathBase, datastore)
   Log('Set suspend directory to %s and added disk in %s' %
       (suspendDir, diskDir))
   vm.PowerOn(vm1)
   suspendFullPath = ResolveDsPath(vm1, suspendDir)
   diskFullPath = ResolveDsPath(vm1, diskDir)
   found = CheckInPolicy(domainName, [(suspendFullPath, 3), (diskFullPath, 3)])
   if len(found) != 2:
      raise Exception('Did not find all expected permissions. Found: %s' %
                      ', '.join(found))
   Log('Suspending VM')
   vm.Suspend(vm1)
   suspendFiles = os.listdir(suspendFullPath)
   if len(suspendFiles) == 0:
      raise Exception('Did not find suspend image in %s' % suspendFullPath)
   Log('Resume VM, power off and clean up')
   vm.PowerOn(vm1)
   vm.PowerOff(vm1)
   # Reset suspend directory, remove added disk and clean up directories
   cspec = Vim.Vm.ConfigSpec()
   files = Vim.Vm.FileInfo()
   files.SetSuspendDirectory('ds://')
   cspec.SetFiles(files)
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(cspec, diskDev, fileOp)
   vm.Reconfigure(vm1, cspec)
   for directory in (suspendDir, diskDir):
      try:
         vimutil.InvokeAndTrack(fileManager.Delete, datastorePath=directory,
                                fileType=Vim.FileManager.FileType.File)
      except Vim.fault.FileNotFound:
         pass

def TestOnlineReconfigure(vm1, datastore=None):
   domainName = 'hostd' + str(vm1._GetMoId())
   vmxPath = vm1.GetSummary().GetConfig().GetVmPathName()

   toolsIso = '/vmimages/tools-isoimages/linux.iso'
   if os.path.isfile(toolsIso):
      Log('Test hot-adding a CDROM backed by an ISO')
      toolsIsoRP = os.path.realpath(toolsIso)
      assert(not CheckInPolicy(domainName, [(toolsIsoRP, 1)]))
      vm.PowerOn(vm1)
      cdromDev, ctlr = AddCdromISO(vm1, toolsIso)
      found = CheckInPolicy(domainName, [(toolsIsoRP, 1)])
      if len(found) != 1:
         DumpFilePolicy(domainName)
         raise Exception('Did not find cdrom image permission')
      # Remove cdrom device
      cspec = Vim.Vm.ConfigSpec()
      vmconfig.RemoveDeviceFromSpec(cspec, cdromDev)
      vm.Reconfigure(vm1, cspec)
      found = CheckInPolicy(domainName, [(toolsIsoRP, 1)], True)
      if len(found) > 0:
         DumpFilePolicy(domainName)
         raise Exception('Found unexpected cdrom image permission')
      vm.PowerOff(vm1)
      cspec = Vim.Vm.ConfigSpec()
      vmconfig.RemoveDeviceFromSpec(cspec, ctlr)
      vm.Reconfigure(vm1, cspec)

   Log('Test hot-adding a serial device backed by a symlink')
   pathBase = os.path.dirname(vmxPath)
   serialDev = AddSerialPipeBacked(vm1)
   vm.PowerOn(vm1)
   origPolicy = RetrieveFilePolicy(domainName)
   serialDev, serialPath, symlink = AddEditSerialSymlinkFile(vm1, pathBase,
                                                             serialDev)
   assert(serialPath not in origPolicy)
   found = CheckInPolicy(domainName, [(serialPath, 3)])
   if len(found) != 1:
      DumpFilePolicy(domainName)
      raise Exception('Did not find serial log permission')
   # Change backing of serial device
   cspec = Vim.Vm.ConfigSpec()
   backing = Vim.Vm.Device.VirtualSerialPort.FileBackingInfo()
   backing.SetFileName(pathBase + "/newSerial.log")
   serialDev.SetBacking(backing)
   vmconfig.AddDeviceToSpec(cspec, serialDev,
                            Vim.Vm.Device.VirtualDeviceSpec.Operation.edit)
   vm.Reconfigure(vm1, cspec)
   found = CheckInPolicy(domainName, [(serialPath, 3)], True)
   if len(found) > 0:
      DumpFilePolicy(domainName)
      raise Exception('Found unexpected serial log permission')
   vm.PowerOff(vm1)
   # Remove serial device
   cspec = Vim.Vm.ConfigSpec()
   vmconfig.RemoveDeviceFromSpec(cspec, serialDev)
   vm.Reconfigure(vm1, cspec)
   os.unlink(symlink)
   try:
      os.unlink(serialPath)
   except OSError as e:
      if e.errno == errno.ENOENT:
         pass

   Log('Test hot adding a new disk in a different directory')
   vm.PowerOn(vm1)
   origPolicy = RetrieveFilePolicy(domainName)
   diskDev, diskDir = AddDiskExternalDir(vm1, pathBase, datastore)
   diskFullPath = ResolveDsPath(vm1, diskDir)
   assert(diskFullPath not in origPolicy)
   found = CheckInPolicy(domainName, [(diskFullPath, 3)])
   if len(found) != 1:
      raise Exception('Did not find all expected permissions. Found: %s' %
                      ', '.join(found))
   # Remove added disk and clean up directory
   cspec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(cspec, diskDev, fileOp)
   vm.Reconfigure(vm1, cspec)
   found = CheckInPolicy(domainName, [(diskFullPath, 3)])
   if len(found) > 0:
      DumpFilePolicy(domainName)
      raise Exception('Found unexpected disk path permission', True)
   vm.PowerOff(vm1)
   fileManager = GetSi().RetrieveContent().GetFileManager()
   try:
      vimutil.InvokeAndTrack(fileManager.Delete, datastorePath=diskDir,
                             fileType=Vim.FileManager.FileType.File)
   except Vim.fault.FileNotFound:
      pass

def TakeSnapshot(vmH, name, desc):
   vm.CreateSnapshot(vmH, name, desc, False, False)
   snapshotInfo = vmH.GetSnapshot()
   return snapshotInfo.GetCurrentSnapshot()

def SetDeltaDiskBacking(configSpec, idx, parentDisk):
   childDiskBacking = configSpec.GetDeviceChange()[idx].GetDevice().GetBacking()
   parentBacking = Vim.Vm.Device.VirtualDisk.FlatVer2BackingInfo()
   parentBacking.SetFileName(parentDisk)
   childDiskBacking.SetParent(parentBacking)
   childDiskBacking.SetDeltaDiskFormat('redoLogFormat')

def TestLinkedClone(vm1, datastore=None):
   if datastore is None:
      vm1Path = vm1.GetSummary().GetConfig().GetVmPathName()
      m = re.search(r'\[(.+)\]', vm1Path)
      datastore = m.group(1)
   baseName = vm1.GetConfig().GetName()
   parentName = 'LinkedParent_' + baseName;
   vmP = folder.Find(parentName)
   if vmP != None:
      Log('Destroying old parent VM %s' % parentName)
      vmP.Destroy()
   # Create parent VM
   vmP = vm.CreateQuickDummy(parentName, numScsiDisks=2,
                             datastoreName=datastore, diskSizeInMB=1)
   # Create snapshots
   # S1 -> S1C1 -> S1C1C1
   #   `-> S1C2
   S1Snapshot = TakeSnapshot(vmP, 'S1', 'S1 is the first snaphost')
   Log('Create Snapshot S1 for parent VM')

   S1C1Snapshot = TakeSnapshot(vmP, 'S1-C1', 'S1-C1 is the first child of S1')
   Log('Create Snapshot S1C1 for parent VM')

   S1C1C1Snapshot = TakeSnapshot(vmP, 'S1-C1-C1',
                                 'S1-C1-C1 is the grand child of S1')
   Log('Create Snapshot S1C1C1 for parent VM')

   # Revert to S1
   vimutil.InvokeAndTrack(S1Snapshot.Revert)
   Log('Reverted parent VM to Snapshot S1')

   S1C2Snapshot = TakeSnapshot(vmP, 'S1-C2', 'S1-C2 is the second child of S1')
   Log('Create Snapshot S1C2 for parent VM')

   # Revert to S1C1C1, so it is the current snapshot
   vimutil.InvokeAndTrack(S1C1C1Snapshot.Revert)
   Log('Reverted parent VM to Snapshot S1C1C1')

   # Get the name of the parent disks
   disks = vmconfig.CheckDevice(S1C2Snapshot.GetConfig(),
                                Vim.Vm.Device.VirtualDisk)
   if len(disks) != 2:
      raise Exception('Failed to find parent disk1')
   parentDisk1 = disks[0].GetBacking().GetFileName()
   disks = vmconfig.CheckDevice(S1C1C1Snapshot.GetConfig(),
                                Vim.Vm.Device.VirtualDisk)
   if len(disks) != 2:
      raise Exception('Failed to find parent disk2')
   parentDisk2 = disks[1].GetBacking().GetFileName()

   # Create a VMC1 whose first disk is linked off S1C2
   child1Name = 'LinkedChild1_' + baseName
   vmC1 = folder.Find(child1Name)
   if vmC1 != None:
      Log('Destroying old child VM %s' % child1Name)
      vmC1.Destroy()

   configSpec = vmconfig.CreateDefaultSpec(name=child1Name,
                                           datastoreName=datastore)
   configSpec = vmconfig.AddScsiCtlr(configSpec)
   configSpec = vmconfig.AddScsiDisk(configSpec, datastorename=datastore,
                                     capacity = 1024)
   SetDeltaDiskBacking(configSpec, 1, parentDisk1)
   resPool = invt.GetResourcePool()
   vmFolder = invt.GetVmFolder()
   vimutil.InvokeAndTrack(vmFolder.CreateVm, configSpec, resPool)
   vmC1 = folder.Find(child1Name)
   vmC1DirName = vmC1.config.files.snapshotDirectory
   Log('Created child VM %s' % child1Name)

   # Create a VMC2 that is linked off S1C1C1
   child2Name = 'LinkedChild2_' + baseName
   vmC2 = folder.Find(child2Name)
   if vmC2 != None:
      Log('Destroying old child VM %s' % child2Name)
      vmC2.Destroy()
   configSpec.SetName(child2Name)
   SetDeltaDiskBacking(configSpec, 1, parentDisk2)
   vimutil.InvokeAndTrack(vmFolder.CreateVm, configSpec, resPool)
   vmC2 = folder.Find(child2Name)
   vmC2DirName = vmC2.config.files.snapshotDirectory
   Log('Created child VM %s' % child2Name)

   # Create snapshot VMC2S1 for VMC2
   TakeSnapshot(vmC2, 'VMC2S1', 'VMC2S1 is VMC2 snaphost')
   Log('Create Snapshot VMC2S1 for VMC2')

   # Create snapshot VMC2S2 for VMC2
   VMC2S2Snapshot = TakeSnapshot(vmC2, 'VMC2S2', 'VMC2S2 is VMC2 snaphost')
   Log('Create Snapshot VMC2S2 for VMC2')

   # Get the disk name of VMC2S2 to use it a parent disk for VMC1
   disks = vmconfig.CheckDevice(VMC2S2Snapshot.GetConfig(),
                                Vim.Vm.Device.VirtualDisk)
   if len(disks) != 1:
      raise Exception('Failed to find parent disk2')
   parentDisk3 = disks[0].GetBacking().GetFileName()

   # Create a delta disk off VMC2S2 on VMC1
   Log('Adding delta disk off VMC2S2 to VMC1')
   configSpec = Vim.Vm.ConfigSpec()
   configSpec = vmconfig.AddScsiDisk(configSpec, datastorename=datastore,
                                     cfgInfo=vmC1.GetConfig())
   SetDeltaDiskBacking(configSpec, 0, parentDisk3)
   vm.Reconfigure(vmC1, configSpec)

   # Final picture
   # vmP: S1 -> S1C1 -> S1C1C1 (disk1, disk2)
   #        `-> S1C2      |
   # vmC2:        |        `-> vmC2S1 -> vmC2S2 (disk1, disk2)
   # vmC1:         `- (disk1)               `- (disk2)

   Log('Verify parent VM domain policy')
   domainP = 'hostd' + str(vmP._GetMoId())
   vmPdir = GetVMHomeDir(vmP)
   vm.PowerOn(vmP)
   found = CheckInPolicy(domainP, [(vmPdir, 3)])
   if len(found) != 1:
      DumpFilePolicy(domainP)
      raise Exception('Did not find parent VM home directory in policy')
   vm.PowerOff(vmP)

   Log('Verify linked child 2 has permission to the parent VM')
   domainC2 = 'hostd' + str(vmC2._GetMoId())
   vmC2dir = GetVMHomeDir(vmC2)
   vm.PowerOn(vmC2)
   found = CheckInPolicy(domainC2, [(vmC2dir, 3), (vmPdir, 1)])
   if len(found) != 2:
      raise Exception('Did not find all expected permission in child 2. ' +
                      'Found: %s' % ', '.join(found))
   vm.PowerOff(vmC2)

   Log('Verify linked child 1 has permission to the parent VM and child 2')
   domainC1 = 'hostd' + str(vmC1._GetMoId())
   vmC1dir = GetVMHomeDir(vmC1)
   vm.PowerOn(vmC1)
   found = CheckInPolicy(domainC1, [(vmC1dir, 3), (vmPdir, 1), (vmC2dir, 1)])
   if len(found) != 3:
      raise Exception('Did not find all expected permission in child 1. ' +
                      'Found: %s' % ', '.join(found))
   vm.PowerOff(vmC1)

   Log('Delete S1C2.  Linked child 1 should not be affected.')
   vimutil.InvokeAndTrack(S1C2Snapshot.Remove, True)
   vm.PowerOn(vmC1)
   found = CheckInPolicy(domainC1, [(vmC1dir, 3), (vmPdir, 1), (vmC2dir, 1)])
   if len(found) != 3:
      raise Exception('Did not find all expected permission in child 1. ' +
                      'Found: %s' % ', '.join(found))
   vm.PowerOff(vmC1)

   Log('Remove disk1 from linked child 1. Verify policy does not change.')
   disks = vmconfig.CheckDevice(vmC1.GetConfig(), Vim.Vm.Device.VirtualDisk)
   disk1 = None
   for disk in disks:
      if disk.backing.parent.fileName == parentDisk1:
         disk1 = disk
   if disk1 is None:
      raise Exception('Did not find disk based on %s' % parentDisk1)
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, disk1, fileOp)
   vm.Reconfigure(vmC1, configSpec)
   vm.PowerOn(vmC1)
   found = CheckInPolicy(domainC1, [(vmC1dir, 3), (vmPdir, 1), (vmC2dir, 1)])
   if len(found) != 3:
      raise Exception('Did not find all expected permission in child 1. ' +
                      'Found: %s' % ', '.join(found))
   vm.PowerOff(vmC1)

   Log('Destroy linked child 2. Verify policy of linked child 1.')
   vm.Destroy(vmC2)
   vm.PowerOn(vmC1)
   found = CheckInPolicy(domainC1, [(vmC1dir, 3), (vmPdir, 1), (vmC2dir, 1)])
   if len(found) != 3:
      raise Exception('Did not find all expected permission in child 1. ' +
                      'Found: %s' % ', '.join(found))
   vm.PowerOff(vmC1)

   Log('Re-create linked child 2 by hot-adding disks based off S1C1C1.')
   configSpec = vmconfig.CreateDefaultSpec(name=child2Name,
                                           datastoreName=datastore)
   configSpec = vmconfig.AddScsiCtlr(configSpec)
   configSpec = vmconfig.AddScsiDisk(configSpec, datastorename=datastore,
                                     capacity=1024)
   vimutil.InvokeAndTrack(vmFolder.CreateVm, configSpec, resPool)
   vmC2 = folder.Find(child2Name)
   domainC2 = 'hostd' + str(vmC2._GetMoId())
   vmC2dir = GetVMHomeDir(vmC2)
   vm.PowerOn(vmC2)
   found = CheckInPolicy(domainC2, [(vmC2dir, 3)])
   if len(found) != 1:
      DumpFilePolicy(domainC2)
      raise Exception('Did not find expected permission in recreated child 2.')
   configSpec = Vim.Vm.ConfigSpec()
   configSpec = vmconfig.AddScsiDisk(configSpec, datastorename=datastore,
                                     capacity=1024, cfgInfo=vmC2.GetConfig())
   SetDeltaDiskBacking(configSpec, 0, parentDisk2)
   vimutil.InvokeAndTrack(vmC2.Reconfigure, configSpec)
   found = CheckInPolicy(domainC2, [(vmC2dir, 3), (vmPdir, 1)])
   if len(found) != 2:
      raise Exception('Did not find all expected permission in recreated ' +
                      'child 2. Found: %s' % ', '.join(found))
   Log('Hot-remove newly added delta disk')
   disks = vmconfig.CheckDevice(vmC2.GetConfig(), Vim.Vm.Device.VirtualDisk)
   deltaDisk = None
   for disk in disks:
      if disk.backing.parent and disk.backing.parent.fileName == parentDisk2:
         deltaDisk = disk
         break
   assert(deltaDisk is not None)
   configSpec = Vim.Vm.ConfigSpec()
   fileOp = Vim.Vm.Device.VirtualDeviceSpec.FileOperation.destroy
   vmconfig.RemoveDeviceFromSpec(configSpec, deltaDisk, fileOp)
   vimutil.InvokeAndTrack(vmC2.Reconfigure, configSpec)
   found = CheckInPolicy(domainC2, [(vmPdir, 1)], True)
   if len(found) > 0:
      DumpFilePolicy(domainC2)
      raise Exception('Found unexpected parent disk dir permission')
   vm.PowerOff(vmC2)

   # Clean up VMs
   vm.Destroy(vmC1)
   vm.Destroy(vmC2)
   vm.Destroy(vmP)
   shutil.rmtree(vmC2dir, ignore_errors=True)
   shutil.rmtree(vmC1dir, ignore_errors=True)
   shutil.rmtree(vmPdir, ignore_errors=True)

def TestIllegalOptions(vm1):
   bldType = os.environ.get('VMBLD', '') or os.environ.get('BLDTYPE', '')
   if bldType != 'obj':
      Log('Test require obj build')
      return vm1
   vmname = vm1.GetSummary().GetConfig().GetName()
   cfg = vm1.GetSummary().GetConfig().GetVmPathName()
   vm.CreateSnapshot(vm1, "backup", "backup", False, False)
   for v in ['', ' with reload']:
      Log('Testing illegal config file modification%s' % v)
      for i in range(3):
         illegalOpt = Vim.Option.OptionValue(
                         key='vmx.test.sandbox.illegalOption', value=str(i))
         nthWriteOpt = Vim.Option.OptionValue(key='vmx.test.sandbox.nthWrite',
                                              value='%d' % (2 + i))
         cspec = Vim.Vm.ConfigSpec(extraConfig=[nthWriteOpt, illegalOpt])
         task = vm.Reconfigure(vm1, cspec)
         vm.PowerOn(vm1)
         if v == ' with reload':
            try:
               vm1.Reload()
            except:
               Log('Illegal options detected before Reload')
               pass
         time.sleep(10)
         if vm1.runtime.powerState != Vim.VirtualMachine.PowerState.poweredOff:
            raise Exception('VM unexpectedly still powered on (option %d)' % i)
         try:
            vm.PowerOn(vm1)
            raise Exception('PowerOn is allowed unexpectedly (option %d)' % i)
         except:
            pass
         vm1.Unregister()
         folder.Register(cfg)
         vm1 = folder.Find(vmname)
         vm.RevertToCurrentSnapshot(vm1)
   return vm1

def HostdMemSize(si):
   # Get hostd virtual memory size in KB
   # Note: This indirectly test the SystemDebugManager, and PyVmomiServer code
   #       used by SystemDebugManager
   hostSystem = host.GetHostSystem(si)
   internalCfgMgr = hostSystem.RetrieveInternalConfigManager()
   if not internalCfgMgr.systemDebugManager:
      return 0

   procInfos = internalCfgMgr.systemDebugManager.QueryProcessInfo()
   for procInfo in procInfos:
      if procInfo.processKey == 'hostd':
         return procInfo.virtualMemSize
   return 0

def RunTests(argv):
   global about

   parser = argparse.ArgumentParser(add_help=False)
   parser.add_argument('-h', '--host', default='localhost', help='Host name')
   parser.add_argument('-u', '--user', default='root', help='User name')
   parser.add_argument('-p', '--pwd', default='', help='Password')
   parser.add_argument('-o', '--port', default=443, type=int, help='Port')
   parser.add_argument('-i', '--numiter', default=1, type=int,
                       help='Iterations')
   parser.add_argument('-d', '--datastore', help='Datastore')
   parser.add_argument('-v', '--volume', help='VMFS volume')
   parser.add_argument('-c', '--cleanup', default=False, action='store_true',
                       help='Try to clean up test VMS from prvious runs')
   parser.add_argument('-?', '--help', action='help', help='Usage')

   options = parser.parse_args(argv)

   # Connect
   si = SmartConnect(host=options.host,
                     user=options.user,
                     pwd=options.pwd,
                     port=options.port)
   atexit.register(Disconnect, si)
   about = si.content.about
   status = "PASS"

   if about.productLineId == 'ws':
      Log('This test is ESX only')
      sys.exit(-1)

   if host.IsHostMockup(GetSi()):
      Log('This test does not support mockup hosts')
      sys.exit(1)

   # Determine the datastore name
   if options.datastore and options.volume:
      Log("Cannot specify both datastore and volume")
      sys.exit(-1)
   elif options.datastore:
      datastore = options.datastore
      Log("Using specified datastore: '%s'" % datastore)
   elif options.volume:
      # Convert absolute volume path to (dsName, relPath) tuple to get dsName
      Log("Trying to determine datastore name for volume: '%s'" % options.volume)
      try:
         datastore = path.FsPathToTuple(options.volume)[0]
         Log("Using datastore: '%s'" % datastore)
      except path.FilePathError as e:
         Log("Could not determine datastore name for volume: '%s'" % options.volume)
         sys.exit(-1)
   else:
      Log("No datastore or volume specified, test will choose one")
      datastore = None

   # To avoid confusion with other 'vmware' modules, set sys.path temporarily
   origPath = sys.path
   sys.path = ['/lib64/python3.5', '/lib64/python3.5/plat-linux2',
               '/lib64/python3.5/lib-tk', '/lib64/python3.5/lib-old',
               '/lib64/python3.5/lib-dynload',
               '/lib64/python3.5/site-packages/setuptools-0.6c11-py2.6.egg',
               '/lib64/python3.5/site-packages']
   global vsi
   import vmware.vsi as vsi
   sys.path = origPath

   Log("Hostd memory : %d KB" % HostdMemSize(si))

   resultsArray = []

   for i in range(options.numiter):
      bigClock = StopWatch()
      try:
         try:
            # Find the vm without tools
            newName = VM_NAME_PREFIX + '_' + str(i)
            vm2 = folder.Find(newName)
            if vm2 != None:
               if options.cleanup:
                  Log("Cleaning up old vm with name: " + newName)
                  try:
                     vm.PowerOff(vm2)
                  except: pass
                  vm.Destroy(vm2)
               else:
                  Log("Please cleanup unit test vms from previous runs")
                  sys.exit(-1)
            ph = Phase()

            # Create a simple vm
            vm2 = vm.CreateQuickDummy(newName, 1, datastoreName=datastore)
            ph.SetPhase("Create VM on " + newName)

            TestInitialFilePolicy(vm2, datastore)
            ph.SetPhase("Initial file policy tests")

            TestOnlineReconfigure(vm2, datastore)
            ph.SetPhase("Online reconfigure tests")

            TestLinkedClone(vm2, datastore)
            ph.SetPhase("Linked clone tests")

            vm2 = TestIllegalOptions(vm2)
            ph.SetPhase("Illegal options tests")

            vm.Destroy(vm2)
            ph.SetPhase("Destroy vm called " + newName)

            status = "PASS"

         finally:
            bigClock.finish("iteration " + str(i))
            Log("Hostd memory after iteration %d : %d KB" % \
                                                         (i, HostdMemSize(si)))

      except Exception as e:
         Log("Caught exception : " + str(e))
         traceback.print_exc()
         status = "FAIL"

      Log("TEST RUN COMPLETE: " + status)
      resultsArray.append(status)

   return_code = 0
   Log("Results for each iteration: ")
   for i in range(len(resultsArray)):
      if resultsArray[i] == "FAIL":
         return_code = -1
      Log("Iteration " + str(i) + ": " + resultsArray[i])

   return return_code


# Start program
if __name__ == "__main__":
   sys.exit(RunTests(sys.argv[1:]))
