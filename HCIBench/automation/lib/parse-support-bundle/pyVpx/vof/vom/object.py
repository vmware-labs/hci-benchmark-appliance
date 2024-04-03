#!/usr/bin/python

from pyVmomi import Vmodl, Vim

class VirtualMachine:
   def __init__(self, vmMoRef):
      self._vmMoRef = vmMoRef

   def _GetMoRef(self):
      return self._vmMoRef

   def _GetRef(self):
      return self._vmMoRef

   def GetConfig(self):
      return self._vmMoRef.GetConfig()

   def ToIdString(self):
      vm = self._vmMoRef
      return "(vom.object.VirtualMachine) %s:%s" % (vm._GetType(), vm._GetMoId())

   def __repr__(self):
      return "(vom.object.VirtualMachine) %s" % self._vmMoRef)

class VirtualDisk:
   def __init__(self, vmMoRef, doRef):
      self._vmMoRef = vmMoRef
      self._doRef = doRef

   def _GetRef(self):
      return self._doRef

   def ToIdString(self):
      vm = self._vmMoRef
      disk = self._doRef
      return "(vom.object.VirtualDisk) %s:%s" % (vm._GetMoId(), disk.GetDeviceInfo().GetLabel())

   def __repr__(self):
      return "(vom.object.VirtualDisk) %s:%s" % (self._vmMoRef, self._doRef)

class VirtualCdrom:
   def __init__(self, vmMoRef, doRef):
      self._vmMoRef = vmMoRef
      self._doRef = doRef

   def _GetRef(self):
      return self._doRef

   def ToIdString(self):
      vm = self._vmMoRef
      disk = self._doRef
      return "(vom.object.VirtualCdrom) %s:%s" % (vm._GetMoId(), disk.GetDeviceInfo().GetLabel())

   def __repr__(self):
      return "(vom.object.VirtualCdrom) %s:%s" % (self._vmMoRef, self._doRef)

