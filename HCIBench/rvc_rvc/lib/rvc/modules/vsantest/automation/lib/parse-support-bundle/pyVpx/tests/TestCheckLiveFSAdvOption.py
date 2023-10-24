"""
Warning:
This test will clobber all the VMFS volumes that it finds on the
server!!!

Test Prerequisites:
1. Need at least 6 blank disks.
2. Make sure before the test "checkLiveFSUnresolvedVolume" option is not set or set to true
    in hostd config.xml under "config/plugins/hostsvc/storage"

"""

from __future__ import print_function

from optparse import OptionParser
import traceback
from pyVmomi import Vim
import pyVim
from pyVim.connect import Connect, Disconnect, GetSi
import pyVim.configSerialize
import popen2
import sys
import time
import atexit


SLEEP_DUR_TO_CHECK_FSLIVENESS = 16

def ClearDisk(lun, storageSys):
      print ("Clearing partitions on disk %s." % lun.devicePath)
      storageSys.UpdateDiskPartitions(lun.devicePath, Vim.Host.DiskPartitionInfo.Specification())


def SnapshotDisk(hostname, diskSrc, diskDst):
   print("Simulating creation of disk snapshot from %s to %s."
         % (diskSrc.devicePath, diskDst.devicePath))

   cmd = "ssh root@%s dd if=%s of=%s bs=%s count=%d conv=notrunc" % (hostname,
                                                                     diskSrc.devicePath,
                                                                     diskDst.devicePath,
                                                                     "1M",
                                                                     1024)
   print("$ %s" % cmd)
   out = []
   (stdout, stdin) = popen2.popen4(cmd)
   stdin.close()
   for line in stdout:
      out.append(line)
   stdout.close()
   sys.stdout.write("".join(out))

def CreateVmfsDatastore(volName, lun, hostSys):
   print("Creating VMFS Datastore %s on disk %s." % (volName, lun.devicePath))

   datastoreSys = hostSys.configManager.datastoreSystem
   storageSys = hostSys.configManager.storageSystem

   # Get the partitioning option that creates VMFS that takes up the entire LUN:
   partitionOption = [option.info for option in datastoreSys.QueryVmfsDatastoreCreateOptions(lun.devicePath) if isinstance(option.info, Vim.Host.VmfsDatastoreOption.AllExtentInfo)][0]

   # Convert the partition block range into a partition spec
   partitionSpec = storageSys.ComputeDiskPartitionInfo(lun.devicePath, partitionOption.layout).spec

   # Build VmfsDatastoreCreateSpec
   vmfsVolumeSpec = \
      Vim.Host.VmfsVolume.Specification(majorVersion=3,
                                       volumeName=volName,
                                       extent=Vim.Host.ScsiDisk.Partition(diskName=lun.canonicalName,
                                       partition=partitionOption.vmfsExtent.partition))

   vmfsDatastoreCreateSpec = \
      Vim.Host.VmfsDatastoreCreateSpec(diskUuid=lun.uuid, partition=partitionSpec, vmfs=vmfsVolumeSpec)

   # Create a VMFS datatstore
   datastore = datastoreSys.CreateVmfsDatastore(vmfsDatastoreCreateSpec)
   return datastore


def RunTest(argv):
   parser = OptionParser(add_help_option=False)
   parser.add_option('-h', '--host', dest='host', help='Host name', default='localhost')
   parser.add_option('-u', '--user', dest='user', help='User name', default='root')
   parser.add_option('-p', '--pwd', dest='pwd', help='Password')
   parser.add_option('-o', '--port', dest='port', help='Port',default=443, type='int')
   parser.add_option('-?', '--help', '--usage', action='help', help='Usage information')

   (options, args) = parser.parse_args(argv)

   si = Connect(host=options.host,
               user=options.user,
               pwd=options.pwd,
               port=options.port,
               version="vim.version.version9")

   hostSys = si.content.rootFolder.childEntity[0].hostFolder.childEntity[0].host[0]
   storageSys = hostSys.configManager.storageSystem
   # Lets get all disks presented to the host.
   luns = \
      [lun for lun in storageSys.storageDeviceInfo.scsiLun if isinstance(lun, Vim.Host.ScsiDisk)]

   if len(luns) < 6:
      print("Number of Luns %s" % len(luns))
      raise Exception("Minimum 6 luns are required for the Test.")

   # CLEANUP: Clear all disks
   print("All disks on server will be clobbered. Are you sure you want to continue? [Y] (Y/N)")
   doClearDisk = sys.stdin.readline()
   if doClearDisk[0] == 'N':
      return 1

   for lun in luns:
      ClearDisk(lun,storageSys)

   # Create VMFS datastores on first half og the luns
   for i in range(0,len(luns)/2):
      CreateVmfsDatastore("originalLun" + str(i),luns[i],hostSys)

   # Create Snapshot Disks
   j=0
   for i in range(len(luns)/2,(len(luns)/2)*2):
      SnapshotDisk(options.host, luns[j], luns[i]);
      j=j+1

   print("Rescanning VMFS volumes")
   storageSys.RescanVmfs()

   # Query for unresolved vmfs volumes.
   print("Calling QueryUnresolvedVmfsVolumes")
   queryStartTime = time.time()
   beforeFlagUnresolvedVmfsVolumes = storageSys.QueryUnresolvedVmfsVolume()
   print(beforeFlagUnresolvedVmfsVolumes)
   queryEndTime = time.time()

   totalQueryTimeBeforeFlagSet = queryEndTime - queryStartTime
   print("checkLiveFSUnresolvedVolume=true/unset: QueryUnresolvedVmfsVolume call duration: %s"
         % str(totalQueryTimeBeforeFlagSet))

   Disconnect(si)

   print("Set checkLiveFSUnresolvedVolume option in hostd config.xml under "
         "config/plugins/hostsvc/storage to false, restart hostd and then press ENTER")
   sys.stdin.readline()

   print("Reconnecting to Host")
   si = Connect(host=options.host,
               user=options.user,
               pwd=options.pwd,
               port=options.port,
               version="vim.version.version9")
   atexit.register(Disconnect, si)

   hostSys = si.content.rootFolder.childEntity[0].hostFolder.childEntity[0].host[0]
   storageSys = hostSys.configManager.storageSystem

   # Query for unresolved vmfs volumes.
   print("Calling QueryUnresolvedVmfsVolumes again.")
   queryStartTime = time.time()
   afterFlagUnresolvedVmfsVolumes = storageSys.QueryUnresolvedVmfsVolume()
   print(afterFlagUnresolvedVmfsVolumes)
   queryEndTime = time.time()

   totalQueryTimeAfterFlagSet = queryEndTime - queryStartTime

   print("checkLiveFSUnresolvedVolume=false: QueryUnresolvedVmfsVolume call duration: %s"
         % totalQueryTimeAfterFlagSet)

   # Verification
   if len(afterFlagUnresolvedVmfsVolumes) != len(beforeFlagUnresolvedVmfsVolumes):
      raise Exception("QueryUnresolvedVmfsVolume call result before and after option is set do not match.");

   print("QueryUnresolvedVmfsVolume call results match for checkLiveFSUnresolvedVolume set to true & false")

   if totalQueryTimeBeforeFlagSet < (len(beforeFlagUnresolvedVmfsVolumes) * SLEEP_DUR_TO_CHECK_FSLIVENESS):
      raise Exception("checkLiveFSUnresolvedVolume=true/unset: QueryUnresolvedVmfsVolume call not checking for liveness")

   # QueryUnresolvedVmfsVolumes call duration without checking liveness.
   queryProcessingTime = \
      totalQueryTimeBeforeFlagSet - (len(beforeFlagUnresolvedVmfsVolumes) * SLEEP_DUR_TO_CHECK_FSLIVENESS)

   # 5 seconds leverage for different processing time based on load on ESX host
   if totalQueryTimeAfterFlagSet > queryProcessingTime + 5:
      raise Exception("checkLiveFSUnresolvedVolume=false, QueryUnresolvedVmfsVolume call \
         taking longer than expected. Expected Duration = %s" % (queryProcessingTime + 5))

   print("checkLiveFSUnresolvedVolume=false: QueryUnresolvedVmfsVolume call as "
         "expected not checking for liveness and finished in acceptable duration.")

   print("TEST: PASSED")

   return 0

#Start program
if __name__ == "__main__":
   sys.exit(RunTest(sys.argv[1:]))
