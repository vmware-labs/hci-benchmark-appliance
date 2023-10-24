from __future__ import print_function

from pyVmomi import vim
from pyVim import connect
from pyVim import folder
from pyVim import host
from pyVim import vm
from pyVim import vmconfig
from pyVim import task
import string
import random

def GetBackingInfo(backingType):
   if backingType == 'flat':
      return vim.vm.Device.VirtualDisk.FlatVer2BackingInfo()
   if backingType == 'seSparse':
      return vim.vm.Device.VirtualDisk.SeSparseBackingInfo()


def test(si, delta, backingType, vmxVersion, ds):
   suffix = ''.join(random.choice(string.letters + string.digits) for i in xrange(8))

   vm1Name = '-'.join(['LinkedParent', suffix])
   print('Creating %s VM on %s' % (vm1Name, ds))
   task.WaitForTasks([vm1.Destroy() for vm1 in folder.GetVmAll() if vm1.name == vm1Name])
   vm1 = vm.CreateQuickDummy(vm1Name, numScsiDisks=1, datastoreName=ds, diskSizeInMB=1,
                             vmxVersion=vmxVersion, backingType=backingType)
   vm1DirName = vm1.config.files.snapshotDirectory

   print('Creating Snapshot S1 for %s' % vm1Name)
   vm.CreateSnapshot(vm1, 'S1', '', False, False)
   s1 = vm1.snapshot.currentSnapshot

   disks = vmconfig.CheckDevice(s1.config, vim.vm.Device.VirtualDisk)
   if len(disks) != 1:
      raise Exception('Failed to find parent disk from snapshot')

   parent = disks[0].backing

   vm2Name = '-'.join(['LinkedChild', suffix])
   print('Creating %s VM on %s' % (vm2Name, ds))
   task.WaitForTasks([vm2.Destroy() for vm2 in folder.GetVmAll() if vm2.name == vm2Name])
   vm2 = vm.CreateQuickDummy(vm2Name, datastoreName=ds, vmxVersion=vmxVersion)
   vm2DirName = vm2.config.files.snapshotDirectory

   configSpec = vim.vm.ConfigSpec()
   configSpec = vmconfig.AddScsiCtlr(configSpec)
   configSpec = vmconfig.AddScsiDisk(configSpec, datastorename = ds, capacity = 1024,
                                     backingType = backingType)
   child = configSpec.deviceChange[1].device.backing
   child.parent = parent
   child.deltaDiskFormat = delta

   # this edit is expected to fail
   configSpec = vmconfig.AddFloppy(configSpec, type="image",
                                   backingName= "[] /these/are/not/the/floppy/images/you/are/looking/for.flp")
   floppy = configSpec.deviceChange[2].device
   floppy.backing = None

   print('Reconfigure %s (1) adding a disk backed by snapshot of %s and (2) '
         'adding floppy backed by non-existent image. Expecting a failure'
         % (vm2Name, vm1Name))
   try:
      vm.Reconfigure(vm2, configSpec)
   except Exception as e:
      pass
   else:
      raise Exception('Expected exception during %s reconfigure. But it succeeded instead' % vm2Name)

   print('Destroying %s' % vm2Name)
   vm.Destroy(vm2)
   print('Destroying %s' % vm1Name)
   vm.Destroy(vm1)

   hostSystem = host.GetHostSystem(si)
   datastoreBrowser = hostSystem.GetDatastoreBrowser()

   try:
      task.WaitForTask(datastoreBrowser.Search(vm1DirName))
   except vim.fault.FileNotFound:
      pass
   else:
      raise Exception("Expected that '%s' will be gone but it still present" % vm1DirName)

   try:
      task.WaitForTask(datastoreBrowser.Search(vm2DirName))
   except vim.fault.FileNotFound:
      pass
   else:
      raise Exception("Expected that '%s' will be gone but it still present" % vm2DirName)


def main():
   from optparse import OptionParser
   parser = OptionParser(add_help_option=False)
   parser.add_option('-h', '--host',            dest='host',                         default='localhost')
   parser.add_option('-u', '--user',            dest='user',                         default='root')
   parser.add_option('-p', '--pwd',             dest='pwd',                          default='')
   parser.add_option('-d', '--ds',              dest='ds',                           default='storage1')
   parser.add_option('-f', '--delta',           dest='delta',                        default='redoLogFormat')
   parser.add_option('-b', '--backingType',     dest='backing',                      default='flat')
   parser.add_option('-v', '--vmxVersion',      dest='vmx',                          default='vmx-08')
   parser.add_option('-?', '--help',            dest='usage',   action='store_true', default=False)
   args, _ = parser.parse_args()

   if args.usage:
      args.print_usage()
      parser.exit(0)

   with connect.SmartConnection(host=args.host, user=args.user, pwd=args.pwd) as si:
      status = None
      try:
         test(si, args.delta, args.backing, args.vmx, args.ds)
      except Exception as e:
         status = 'Failure: ' + str(e)
         raise
      else:
         status = 'Success'
      finally:
         print('TEST RUN COMPLETE: %s' % status)


if __name__ == '__main__':
   main()
