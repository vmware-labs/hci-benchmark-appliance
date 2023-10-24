class NoSuchVirtualMachineError(Exception):
   def __init__(self, vmname):
      msg = 'No such VM: {0}'.format(vmname)
      Exception.__init__(self, msg)

class NoSuchDiskError(Exception):
   def __init__(self, vm, diskKey=None, diskIndex=None):
      vmname = vm.GetConfig().GetName()
      msg = 'No such disk for vm {0}: '.format(vmname)
      if diskKey is not None:
         msg += 'disk key {0}'.format(diskKey)
      else:
         msg += 'disk index {0}'.format(diskIndex)
      Exception.__init__(self, msg)

class ConfigError(Exception):
   pass

class ConnectionError(Exception):
   pass
