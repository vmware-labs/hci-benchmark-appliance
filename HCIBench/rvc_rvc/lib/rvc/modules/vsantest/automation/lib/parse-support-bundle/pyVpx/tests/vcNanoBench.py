# Execute VC NanoBench
# Usage: py.sh vcNanoBench.py -v <vc> -u <user> -p <password>
#                             -h <host-name> -v <vm-name>

from __future__ import print_function

from pyVmomi import Vim, Vpx
from pyVim import connect
from optparse import OptionParser
from socket import gethostbyaddr, herror
from time import sleep
import sys

def FindHostByName(si, name):
   ''' Find a host specified by its name '''
   if name is None:
      return None

   idx = si.content.searchIndex
   host = idx.FindByIp(None, name, False) or idx.FindByDnsName(None, name, False)

   if not host:
      try:
         hostName = gethostbyaddr(name)[0]
         host = idx.FindByDnsName(None, hostName, False)
      except herror as err:
         host = None

   return host

def FindVmByName(si, name):
   ''' Find a VM specified by its name '''
   if name is None:
      return None

   objView = si.content.viewManager.CreateContainerView(
                si.content.rootFolder, [Vim.VirtualMachine], True)
   for x in objView.GetView():
      if x.name == name:
         return x
   objView.Destroy()
   return None

def AddArgument(key, value, args):
   arg = Vim.KeyValue()
   arg.key = key
   arg.value = str(value)
   args.append(arg)

class NanoBench():
   BENCHMARKS = ['NoopTime',
                 'MoLockTime',
                 'RecursiveMoLockTime',
                 'VpxMutexTime',
                 'VmStateLockTime',
                 'VmacoreRWLockTime',
                 'VmacoreLogTime',
                 'NewVpxTLSTime',
                 'VmacoreTLSRefTime',
                 'GetVmacoreTLSTime',
                 'GetThisThreadTime',
                 'GetMonotonicTime',
                 'ComputeVmOvhdMemTime',
                 'SerializeVmConfigTime',
                 'InvtHostUpdateDBTime',
                 'InvtVmUpdateDBTime',
                 'HostMoUpdateRuntimeTime',
                 'GetMObjectTime',
                 'GetMObjectNameTime',
                 'VmInitialPlacementTime',
                 'VmPowerStateRecordAssignTime',
                 'QueryVMotionCompatibilityTime',
                 'CheckPowerOnTime',
                 'QueryClusterVMotionCompatTime',
                 'CheckClusterPowerOnTime',
                 'DoFullHostSyncTime',
                 'SchedueWorkItemTime',
                 'RecommendClusterResSettingTime',
                 'GetChangesTime']

   def __init__(self, benchMgr, iteration, host, vm):
      self.benchMgr = benchMgr
      self.runList = []
      self.args = []

      if iteration is not None:
         AddArgument("Iteration", iteration, self.args)
      if host is not None:
         AddArgument("HostMoId", host._moId, self.args)
         # We test host MoLock by default
         AddArgument("MoId", host._moId, self.args)
      if vm is not None:
         AddArgument("VmMoId", vm._moId, self.args)
         if host is None:
            # We test vm MoLock if host is not specified
            AddArgument("MoId", vm._moId, self.args)

   def setRunList(self, csv):
      ''' Set the run list based on csv. If None, run all. '''
      if csv is None:
         self.runList = self.BENCHMARKS[:]
         return
      else:
         self.runList = csv.split(',')

   def run(self):
      ''' Run the benchmarks '''
      for b in self.runList:
         try:
            if b == 'VmacoreRWLockTime':
               modes = ['default', 'fair', 'unfair']
               for mode in modes:
                  args = self.args[:]
                  AddArgument('Mode', mode, args)
                  print('%s, Mode=%s' % (self.benchMgr.Execute(b, args), mode))
                  print('')
                  sleep(2)
            else:
               print(self.benchMgr.Execute(b, self.args))
               print('')
               sleep(2)
         except:
            pass

def main():
   parser = OptionParser()
   parser.add_option('-v', '--vc', dest='vc', default='localhost', help='VC to connect to')
   parser.add_option('-u', '--user', dest='user', default='root', help='User name')
   parser.add_option('-p', '--password', dest='password', default='vmware', help='Password')
   parser.add_option('-e', '--esx', dest='host', help='Host name')
   parser.add_option('-m', '--vm', dest='vm', help='VM name')
   parser.add_option('-i', '--iteration', dest='iteration', default='1000', help='Number of iterations')
   parser.add_option('-b', '--bench', dest='bench', help='comma-separated benchmark names')

   (options, args) = parser.parse_args()
   connect.Connect(host=options.vc, user=options.user,\
                   pwd=options.password, version='vpx.version.version9')
   si = connect.GetSi()
   if si is None:
      return

   vpxSi = Vpx.ServiceInstance("VpxdInternalServiceInstance", si._GetStub())
   benchMgr = vpxSi.debugManager.benchmarkManager
   host = FindHostByName(si, options.host) # could be None
   vm = FindVmByName(si, options.vm) # could be None

   nanobench = NanoBench(benchMgr, options.iteration, host, vm)
   try:
      nanobench.setRunList(options.bench)
      nanobench.run()
   finally:
      si.content.sessionManager.Logout()

if __name__ == "__main__":
   main()
