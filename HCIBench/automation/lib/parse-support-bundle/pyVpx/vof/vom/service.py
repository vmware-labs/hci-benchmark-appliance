#!/usr/bin/python

from pyVmomi import Vmodl, Vim
import vom.proputil

# Get all VMS on the Service Instance
def GetAllVMs(props):
   si = vom.proputil.GetServiceInstance(props["host"], props["port"], props["user"],
                                        props["password"], props["adapter"])

   # XXX Compose a property collector spec that does the same thing
   entities = vom.proputil.GetEntities(si)

   vmlist = filter(lambda x: x._GetType() == "vim.VirtualMachine", entities)

   # Convert to Vom.Object.VirtualMachine
   vmlist = map(lambda x: vom.object.VirtualMachine(x), vmlist)
   
   return vmlist


def VMtoVirtualDisk(vmlist, instanceProps):
   diskList = []
   
   for vm in vmlist:
      configInfo = vm.GetConfig()
      hardware = configInfo.GetHardware()

      for dev in hardware.GetDevice():
         if isinstance(dev, Vim.Vm.Device.VirtualDisk):
            diskList.append(vom.object.VirtualDisk(vm._GetMoRef(), dev))

   return diskList
   


def VMtoVirtualCdrom(vmlist, instanceProps):
   diskList = []
   
   for vm in vmlist:
      configInfo = vm.GetConfig()
      hardware = configInfo.GetHardware()

      for dev in hardware.GetDevice():
         if isinstance(dev, Vim.Vm.Device.VirtualCdrom):
            diskList.append(vom.object.VirtualCdrom(vm._GetMoRef(), dev))

   return diskList

def ToProperty(objlist, propName):
   proplist = []
   return map(lambda o: o._GetRef()._GetProperty(propName), objlist)
   

