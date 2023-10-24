from __future__ import print_function

from pyVmomi import vim
from pyVim import connect
from pyVim import folder
from pyVim import host
from pyVim import invt
from pyVim import vm
from pyVim import vmconfig
from pyVim import task

from time import sleep
from os import path

from string import letters, digits
from random import choice

from pprint import pprint

import sys


def TestRelocateWithSnapshotsWithNonHomeRedoLogDir(si, args):
   vm1name =  'dummy-' + ''.join(choice(letters + digits) for c in xrange(8))

   print('# 1. Find the host and the target datastore(s)')
   host1 = [host1 for host1 in folder.GetHostAll() if not args.host or host1.name.startswith(args.host)][0]
   dc1 = host1.parent
   while True:
      if isinstance(dc1, vim.Datacenter) or not dc1:
         break
      dc1 = dc1.parent
   assert(dc1)
   dsHome   = [ds for ds in host1.datastore if ds.name == args.dsHome][0]
   dsAux    = [ds for ds in host1.datastore if ds.name == args.dsAux][0]
   dsTarget = [ds for ds in host1.datastore if ds.name == args.dsTarget][0]

   print('Using target host: %s' % host1.name)
   print('Using target datacenter: %s' % dc1.name)
   print('Using home datastore: %s' % dsHome.name)
   print('Using aux datastore: %s' % dsAux.name)
   print('Using target datastore: %s' % dsTarget.name)

   if args.interactive:
      raw_input('\nPress Enter to continue ...\n')


   ###
   print('# 2. Creating %s on %s' % (vm1name, dsHome.name))
   vm1 = vm.CreateQuickDummy(vm1name, numScsiDisks=1, datastoreName=dsHome.name, vmxVersion='vmx-07')

   if args.interactive:
      raw_input('\nPress Enter to continue ...\n')


   ###
   print('# 3. Reconfigure VM for snapshot dir on %s' % dsAux.name)
   snapshotDirectory = '[%s] %s-snapshotDir' % (dsAux.name, vm1.name)

   try:
      print('Creating snapshot dir %s ... ' % snapshotDirectory, end=''); sys.stdout.flush()
      si.content.fileManager.MakeDirectory(snapshotDirectory, dc1)
   except:
      print('failed!')
      raise
   else:
      print('done')

   spec = vim.vm.ConfigSpec(
      files = vim.vm.FileInfo(snapshotDirectory = snapshotDirectory),
      extraConfig = [vim.option.OptionValue(key = 'snapshot.redoNotWithParent', value = 'true')])

   try:
      print('Reconfiguring ... ', end=''); sys.stdout.flush()
      vm.Reconfigure(vm1, spec)
   except:
      print('failed!')
      raise
   else:
      print('done')

   if args.interactive:
      raw_input('\nPress Enter to continue ...\n')


   ###
   print('# 4. Create snapshots')

   s1 = None
   for snapshotName in ['S1', 'S1-1', 'S1-1-1', 'S1-1-1-1']:
      try:
         print('Creating snapshot %s ... ' % snapshotName, end=''); sys.stdout.flush()
         vm.CreateSnapshot(vm1, snapshotName, '', False, False)
      except:
         print('failed!')
         raise
      else:
         print('done')

      if not s1:
         s1 = vm1.snapshot.currentSnapshot

   print('Reverting to snapshot S1 ... ', end=''); sys.stdout.flush()
   vm.RevertSnapshot(s1)
   print('done')

   for snapshotName in ['S1-2', 'S1-2-1']:
      try:
         print('Creating snapshot %s ... ' % snapshotName, end=''); sys.stdout.flush()
         vm.CreateSnapshot(vm1, snapshotName, '', False, False)
      except:
         print('failed!')
         raise
      else:
         print('done')

   if args.interactive:
      raw_input('\nPress Enter to continue ...\n')


   ###
   print('# 5. Power cycle')

   try:
      print('Powering on ... ', end=''); sys.stdout.flush()
      vm.PowerOn(vm1)
   except:
      print('failed!')
      raise
   else:
      print('done')
      sleep(1)

   try:
      print('Powering off ... ', end=''); sys.stdout.flush()
      vm.PowerOff(vm1)
   except:
      print('failed!')
      raise
   else:
      print('done')
      sleep(1)

   try:
      print('Powering on ... ', end=''); sys.stdout.flush()
      vm.PowerOn(vm1)
   except:
      print('failed!')
      raise
   else:
      print('done')
      sleep(1)

   try:
      print('Suspending ... ', end=''); sys.stdout.flush()
      vm.Suspend(vm1)
   except:
      print('failed!')
      raise
   else:
      print('done')
      sleep(1)

   print('Current layout:')
   pprint(sorted(f1.name for f1 in vm1.layoutEx.file), width=1000)

   if args.norelocate:
      return

   if args.interactive:
      raw_input('\nPress Enter to continue ...\n')


   ###
   print('# 6. Relocate all to target %s' % dsTarget.name)
   spec = vim.vm.RelocateSpec(
      datastore = dsTarget,
      host = host1,
      disk = [vim.vm.RelocateSpec.DiskLocator(diskId = d1.key, datastore = dsTarget) \
                 for d1 in vm1.config.hardware.device \
                 if isinstance(d1, vim.vm.device.VirtualDisk)
              ])

   try:
      print('Relocating ... ', end=''); sys.stdout.flush()
      vm.Relocate(vm1, spec)
   except:
      print('failed!')
      raise
   else:
      print('done')
   finally:
      print('Current layout:')
      pprint(sorted(f1.name for f1 in vm1.layoutEx.file), width=1000)

   if args.interactive:
      raw_input('\nPress Enter to continue ...\n')


def main():
   from optparse import OptionParser
   parser = OptionParser(add_help_option=False)
   parser.add_option('-t', '--targetVC',   dest='target',     default='localhost',               help='vCenter address')
   parser.add_option('-u', '--user',       dest='user',       default='root',                    help='vCenter username')
   parser.add_option('-p', '--pwd',        dest='pwd',        default='vmware',                  help='vCenter password')
   parser.add_option('-h', '--host',       dest='host',       default=None,                      help='Visor host name')
   parser.add_option('-1', '--dsHome',     dest='dsHome',     default=None,                      help='Home datastore name')
   parser.add_option('-2', '--dsAux',      dest='dsAux',      default=None,                      help='Auxiliary datastore name')
   parser.add_option('-3', '--dsTarget',   dest='dsTarget',   default=None,                      help='Target datastore name')
   parser.add_option('-i', '--interactive',dest='interactive',default=False, action='store_true',help='Interactive mode')
   parser.add_option('-n', '--no-relocate',dest='norelocate', default=False, action='store_true',help='No relocate')
   parser.add_option('-?', '--help',       dest='usage',      default=False, action='store_true',help='This help message')
   args, _ = parser.parse_args()

   if args.usage:
      args.print_usage()
      parser.exit(0)

   if not args.host:
      print('No visor host specified.')
      args.print_usage()
      parser.exit(0)

   if not args.dsHome:
      print('No home datastore specified.')
      args.print_usage()
      parser.exit(0)

   if not args.dsAux:
      print('No auxiliary datastore specified.')
      args.print_usage()
      parser.exit(0)

   if not args.dsTarget:
      print('No target datastore specified.')
      args.print_usage()
      parser.exit(0)

   with connect.SmartConnection(host=args.target, user=args.user, pwd=args.pwd) as si:
      status = None
      try:
         TestRelocateWithSnapshotsWithNonHomeRedoLogDir(si, args)
      except Exception as e:
         status = 'Failure'
         raise
      else:
         status = 'Success'
      finally:
         print('TEST RUN COMPLETE: %s' % status)


if __name__ == '__main__':
   main()
