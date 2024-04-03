from __future__ import print_function

from pyVmomi import vim
from pyVim import connect
from pyVim import folder
from pyVim import vm
from pyVim import vmconfig
from pyVim import task
import string
import random

def testKeyOnlyRemove(si, vmxVersion, ds):
   """This test verifies that it is possible to remove devices by passing
      a VirtualDevice object with only key specified.
      This is a legacy behavior present in Foundry, supported only for compatibility reasons.
      It is not recommended to use this functionality in any products."""

   suffix = ''.join(random.choice(string.letters + string.digits) for i in xrange(8))

   vm1Name = '-'.join(['KeyOnlyRemove', suffix])
   print('Creating %s VM on %s' % (vm1Name, ds))
   task.WaitForTasks([vm1.Destroy() for vm1 in folder.GetVmAll() if vm1.name == vm1Name])
   vm1 = vm.CreateQuickDummy(vm1Name, numScsiDisks = 1, numIdeDisks = 1, diskSizeInMB = 1,
                             nic = 1, cdrom = 1, datastoreName = ds, vmxVersion = vmxVersion)

   print('Testing device removal via VirtualDevice with key set on VM %s' % vm1Name)
   #gather all the devices we want to remove
   devices = [vim.vm.device.VirtualDevice(key=d.key) for d in vm1.config.hardware.device if isinstance(d, (vim.vm.device.VirtualEthernetCard,
                                                                                                           vim.vm.device.VirtualDisk,
                                                                                                           vim.vm.device.VirtualCdrom))]
   #prepare a config spec containing VirtualDevice "abstract" objects with keys we want
   #to remove
   cspec = vim.vm.ConfigSpec()
   for device in devices:
      vmconfig.AddDeviceToSpec(cspec, device, vim.vm.device.VirtualDeviceSpec.Operation.remove)

   #reconfigure the VM
   task.WaitForTask(vm1.Reconfigure(cspec))

   #verify that the devices are removed
   devices = [vim.vm.device.VirtualDevice(key=d.key) for d in vm1.config.hardware.device if isinstance(d, (vim.vm.device.VirtualEthernetCard,
                                                                                                           vim.vm.device.VirtualDisk,
                                                                                                           vim.vm.device.VirtualCdrom))]
   if len(devices) != 0:
      raise Exception("Not all devices were deleted!")

   #destroy the vm
   print('Done testing, destroying %s VM' % vm1Name)
   vm.Destroy(vm1)

def main():
   from optparse import OptionParser
   parser = OptionParser(add_help_option=False)
   parser.add_option('-h', '--host',            dest='host',                         default='localhost')
   parser.add_option('-u', '--user',            dest='user',                         default='root')
   parser.add_option('-p', '--pwd',             dest='pwd',                          default='')
   parser.add_option('-d', '--ds',              dest='ds',                           default='datastore1')
   parser.add_option('-v', '--vmxVersion',      dest='vmx',                          default='vmx-08')
   parser.add_option('-?', '--help',            dest='usage',   action='store_true', default=False)

   args, _ = parser.parse_args()
   if args.usage:
      args.print_usage()
      parser.exit(0)

   with connect.SmartConnection(host=args.host, user=args.user, pwd=args.pwd) as si:
      status = None
      try:
         testKeyOnlyRemove(si, args.vmx, args.ds)
      except Exception as e:
         status = 'Failure: ' + str(e)
         raise
      else:
         status = 'Success'
      finally:
         print('TEST RUN COMPLETE: %s' % status)


if __name__ == '__main__':
   main()
