#!/usr/bin/python
# Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential
## Table definitions for esxcfg-info output.

## Defines a table from an EsxCfgInfoParse
class TableDefinition:
   def __init__(self, tableName, columnDefinitions, buildSpec):
      self.tableName = tableName
      self.columnDefinitions = columnDefinitions
      self.buildSpec = buildSpec

## Defines a column for a table built from an EsxCfgInfoParse
class TableColumnDefinition:
   #
   # @param  name [in] name of the column on the table
   # @param  valueFn [in] function object to access value from a group node
   # @param  sortFn [in] function object to sort elements of the row
   # 
   def __init__(self, name, sortFn = None):
      self.name = name
      self.sortFn = sortFn

## Defines a specification describing how to build a table from an EsxCfgInfoParse
class TableBuildSpec:
   def __init__(self, rowPaths, columnBuilders):
      self.rowPaths = rowPaths
      self.columnBuilders = columnBuilders


## Function objects used to build up a table
class NodeAccess:
   def __init__(self, key):
      self._key = key

   def GetValue(self, groupNode):
      return groupNode.Get(self._key)

## Function objects used to build up a table
class NodeAccessComposer:
   def __init__(self, keys, formatString):
      self._keys = keys
      self._formatString = formatString

      self._access = {}
      for key in self._keys:
         self._access[key] = NodeAccess(key)


   def GetValue(self, groupNode):
      fargs = {}
      for key in self._access:
         fargs[key] = self._access[key].GetValue(groupNode)
      return self._formatString % fargs


## Function objects used to build up a table
class NodeAccessList:
   def __init__(self, keys):
      self._keys = keys

   def GetValue(self, groupNode):
      node = groupNode
      for key in self._keys[:-1]:
         children = node.GetChildrenByName(key)

         if len(children) == 0:
            return "N/A"

         node = children[0]

      return node.Get(self._keys[-1])

## Function objects used to build up a table
class NodeAccessListComposer:
   def __init__(self, keysList, formatString):
      self._keysList = keysList
      self._formatString = formatString

      self._access = {}
      for keyList in self._keysList:
         key = "/".join(keyList)
         self._access[key] = NodeAccessList(keyList)

   def GetValue(self, groupNode):
      fargs = {}
      for key in self._access:
         fargs[key] = self._access[key].GetValue(groupNode)
      return self._formatString % fargs


## Get CPU table definition.
#
# Gets a table specification that can be used to create a table of CPU
# device information.
def GetCpu():
   rowPaths = ["Host", "Hardware Info", "CPU Info", "Cpus", "CpuImpl"]
   columnDefinitions = [ \
      TableColumnDefinition("ID", None),
      TableColumnDefinition("NAME", None),
      TableColumnDefinition("FAMILY", None),
      TableColumnDefinition("MODEL", None),
      TableColumnDefinition("TYPE", None),
      TableColumnDefinition("STEPPING", None),
      TableColumnDefinition("CPU_SPEED", None),
      TableColumnDefinition("BUS_SPEED", None),
      TableColumnDefinition("APIC_ID", None),
      ]

   columnBuilders = {
      "ID": NodeAccess("ID"),
      "NAME": NodeAccess("Name"),
      "FAMILY": NodeAccess("Family"),
      "MODEL": NodeAccess("Model"),
      "TYPE": NodeAccess("Type"),
      "STEPPING": NodeAccess("Stepping"),
      "CPU_SPEED": NodeAccess("CPU Speed"),
      "BUS_SPEED": NodeAccess("Bus Speed"),
      "APIC_ID": NodeAccess("APIC ID"),      
      }
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_CPU_DEVICE", columnDefinitions, buildSpec)

   return tableDefinition


## Get PCI Device table definition.
#
# Gets a table specification that can be used to create a table of PCI
# device information.
def GetPciDevice():
   rowPaths = ["Host", "Hardware Info", "PCI Info", "All Pci Devices", "PCI Device"]
   columnDefinitions = [ \
      TableColumnDefinition("KEY", None),
      TableColumnDefinition("DEVICE_CLASS", None),
      TableColumnDefinition("VENDOR_ID", None),
      TableColumnDefinition("DEVICE_ID", None),
      TableColumnDefinition("SUBSYSTEM_VENDOR_ID", None),
      TableColumnDefinition("SUBSYSTEM_DEVICE_ID", None),
      TableColumnDefinition("BUS", None),
      TableColumnDefinition("SLOT", None),
      TableColumnDefinition("FUNCTION", None),
      TableColumnDefinition("VENDOR_NAME", None),
      TableColumnDefinition("DEVICE_NAME", None),
      ]

   columnBuilders = {
      "KEY": NodeAccessComposer( ["Bus", "Slot", "Function"],
                                 '%(Bus)s:%(Slot)s.%(Function)s'),
      "DEVICE_CLASS": NodeAccess("Device Class"),
      "VENDOR_ID": NodeAccess("Vendor Id"),
      "DEVICE_ID": NodeAccess("Device Id"),
      "SUBSYSTEM_DEVICE_ID": NodeAccess("Sub-Device Id"),
      "SUBSYSTEM_VENDOR_ID": NodeAccess("Sub-Vendor Id"),
      "BUS": NodeAccess("Bus"),
      "SLOT": NodeAccess("Slot"),
      "FUNCTION": NodeAccess("Function"),
      "VENDOR_NAME": NodeAccess("Vendor Name"),
      "DEVICE_NAME": NodeAccess("Device Name"),
      }
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_PCI_DEVICE", columnDefinitions, buildSpec)

   return tableDefinition


## Get PhysicalNic table definition.
#
# Gets a table specification that can be used to create a table of Physical NIC
# device information.
def GetPhysicalNic():
   rowPaths = ["Host", "Network Info", "Physical NICs", "Physical Nic"]
   columnDefinitions = [ \
      TableColumnDefinition("NAME", None),
      TableColumnDefinition("DRIVER", None),
      TableColumnDefinition("LINK_UP", None),
      TableColumnDefinition("MAC_ADDRESS", None),
      TableColumnDefinition("VIRTUAL_MAC_ADDRESS", None),
      TableColumnDefinition("ACTUAL_SPEED", None),
      TableColumnDefinition("ACTUAL_DUPLEX", None),
      TableColumnDefinition("CONFIGURED_SPEED", None),
      TableColumnDefinition("CONFIGURED_DUPLEX", None),
      TableColumnDefinition("MTU", None),
      TableColumnDefinition("NETWORK_HINT", None),
      TableColumnDefinition("PCI_KEY", None),
      TableColumnDefinition("VENDOR_NAME", None),
      TableColumnDefinition("DEVICE_NAME", None),
      ]

   columnBuilders = {
      "NAME": NodeAccess("Name"),
      "DRIVER": NodeAccess("Driver"),
      "LINK_UP": NodeAccess("Link Up"),
      "MAC_ADDRESS": NodeAccess("MAC Address"),
      "VIRTUAL_MAC_ADDRESS": NodeAccess("Virtual MAC Address"),
      "ACTUAL_SPEED": NodeAccess("Actual Speed"),
      "ACTUAL_DUPLEX": NodeAccess("Actual Duplex"),
      "CONFIGURED_SPEED": NodeAccess("Configured Speed"),
      "CONFIGURED_DUPLEX": NodeAccess("Configured Duplex"),
      "MTU": NodeAccess("MTU"),
      "NETWORK_HINT": NodeAccess("Network Hint"),
      "PCI_KEY": NodeAccessListComposer( [ ["PCI Device", "Bus"],
                                           ["PCI Device", "Slot"],
                                           ["PCI Device", "Function"] ],
                                         '%(PCI Device/Bus)s' + ':' +
                                         '%(PCI Device/Slot)s' + '.' +
                                         '%(PCI Device/Function)s'),
      "VENDOR_NAME": NodeAccessList(["PCI Device", "Vendor Name"]),
      "DEVICE_NAME": NodeAccessList(["PCI Device", "Device Name"]),
      }
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_PHYSICAL_NIC", columnDefinitions, buildSpec)

   return tableDefinition


## Get VmkernelNic table definition.
#
# Gets a table specification that can be used to create a table of vmkernel NIC
# information.
def GetVmkernelNic():
   rowPaths = ["Host", "Network Info", "Network Entities", "VMkernel Nic Info", "Kernel Nics", "VmKernel Nic"]
   columnDefinitions = [ \
      TableColumnDefinition("INTERFACE", None),
      TableColumnDefinition("PORT_GROUP", None),
      TableColumnDefinition("MAC_ADDRESS", None),
      TableColumnDefinition("ACTUAL_IP_TYPE", None),
      TableColumnDefinition("ACTUAL_IPV4_ADDRESS", None),
      TableColumnDefinition("ACTUAL_IPV4_BROADCAST", None),
      TableColumnDefinition("ACTUAL_IPV4_NETMASK", None),
      TableColumnDefinition("CONFIGURED_IP_TYPE", None),
      TableColumnDefinition("CONFIGURED_IPV4_ADDRESS", None),
      TableColumnDefinition("CONFIGURED_IPV4_BROADCAST", None),
      TableColumnDefinition("CONFIGURED_IPV4_NETMASK", None),
      TableColumnDefinition("MTU", None),
      ]

   columnBuilders = {
      "INTERFACE": NodeAccess("Interface"),
      "PORT_GROUP": NodeAccess("Port Group"),
      "MAC_ADDRESS": NodeAccess("Mac Address"),
      "ACTUAL_IP_TYPE": NodeAccessList(["Actual IP settings", "Type"]),
      "ACTUAL_IPV4_ADDRESS": NodeAccessList(["Actual IP settings", "IPv4 Address"]),
      "ACTUAL_IPV4_NETMASK": NodeAccessList(["Actual IP settings", "IPv4 Netmask"]),
      "ACTUAL_IPV4_BROADCAST": NodeAccessList(["Actual IP settings", "IPv4 Broadcast"]),
      "CONFIGURED_IP_TYPE": NodeAccessList(["Configured IP settings", "Type"]),
      "CONFIGURED_IPV4_ADDRESS": NodeAccessList(["Configured IP settings", "IPv4 Address"]),
      "CONFIGURED_IPV4_NETMASK": NodeAccessList(["Configured IP settings", "IPv4 Netmask"]),
      "CONFIGURED_IPV4_BROADCAST": NodeAccessList(["Configured IP settings", "IPv4 Broadcast"]),
      "MTU": NodeAccess("MTU"),
      }
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_VMKERNEL_NIC", columnDefinitions, buildSpec)

   return tableDefinition


## Get Virtual Switch table definition.
#
# Gets a table specification that can be used to create a table of vmkernel NIC
# information.
def GetVirtualSwitch():
   rowPaths = ["Host", "Network Info", "Network Entities", "Virtual Switch Info", "Virtual Switches", "Virtual Switch"]
   columnDefinitions = [ \
      TableColumnDefinition("NAME", None),
      TableColumnDefinition("TOTAL_PORTS", None),
      TableColumnDefinition("USED_PORTS", None),
      TableColumnDefinition("CONFIGURED_PORTS", None),
      TableColumnDefinition("MTU", None),
      TableColumnDefinition("UPLINKS", None),
      ]

   columnBuilders = {
      "NAME": NodeAccess("Name"),
      "TOTAL_PORTS": NodeAccess("Total Ports"),
      "USED_PORTS": NodeAccess("Used Ports"),
      "CONFIGURED_PORTS": NodeAccess("Configured Ports"),
      "MTU": NodeAccess("MTU"),
      "UPLINKS": NodeAccess("Uplinks"),
      }
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_VIRTUAL_SWITCH", columnDefinitions, buildSpec)

   return tableDefinition


## Get Port Group table definition.
#
# Gets a table specification that can be used to create a table of vmkernel NIC
# information.
def GetPortGroup():
   rowPaths = ["Host", "Network Info", "Network Entities", "Virtual Switch Info",
               "Virtual Switches", "Virtual Switch", "Port Groups", "Port Group"]
   columnDefinitions = [ \
      TableColumnDefinition("NAME", None),
      TableColumnDefinition("VIRTUAL_SWITCH", None),
      TableColumnDefinition("VLANID", None),
      TableColumnDefinition("ACTIVE_CLIENTS", None),
      ]

   columnBuilders = {
      "NAME": NodeAccess("Name"),
      "VIRTUAL_SWITCH": NodeAccess("Virtual Switch"),
      "VLANID": NodeAccess("Vlan Id"),
      "ACTIVE_CLIENTS": NodeAccess("Active Clients"),
      }
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_PORT_GROUP", columnDefinitions, buildSpec)

   return tableDefinition

# Common hba column definitions and build mappings
hbaColumnDefinitions = [ \
   TableColumnDefinition("NAME", None),
   TableColumnDefinition("DRIVER", None),
   TableColumnDefinition("IS_VIRTUAL", None),
   TableColumnDefinition("CONSOLE_NAME", None),
   TableColumnDefinition("QUEUE_DEPTH", None),
   TableColumnDefinition("PCI_KEY", None),
   TableColumnDefinition("VENDOR_NAME", None),
   TableColumnDefinition("DEVICE_NAME", None),
]

hbaColumnBuilders = {
   "NAME": NodeAccess("Name"),
   "DRIVER": NodeAccess("Driver"),
   "IS_VIRTUAL": NodeAccess("Is Virtual"),
   "CONSOLE_NAME": NodeAccess("Console Name"),
   "QUEUE_DEPTH": NodeAccess("Queue Depth"),
   "PCI_KEY": NodeAccessListComposer( [ ["PCI Device", "Bus"],
                                        ["PCI Device", "Slot"],
                                        ["PCI Device", "Function"] ],
                                      '%(PCI Device/Bus)s' + ':' +
                                      '%(PCI Device/Slot)s' + '.' +
                                      '%(PCI Device/Function)s'),
   "VENDOR_NAME": NodeAccessList(["PCI Device", "Vendor Name"]),
   "DEVICE_NAME": NodeAccessList(["PCI Device", "Device Name"]),
}

## Get Block IDE table definition.
#
# Gets a table specification that can be used to create a table of Block
# SCSI hba information.
def GetBlockIdeInterface():
   rowPaths = ["Host", "Storage Info", "All SCSI Iface", "Block IDE Interface", "SCSI Interface"]

   # Make a copy of the array and table
   columnDefinitions = hbaColumnDefinitions[0:]
   columnBuilders = dict(hbaColumnBuilders)
   
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_BLOCK_IDE_INTERFACE", columnDefinitions, buildSpec)

   return tableDefinition


## Get Parallel SCSI table definition.
#
# Gets a table specification that can be used to create a table of parallel
# SCSI hba information.
def GetParallelScsiInterface():
   rowPaths = ["Host", "Storage Info", "All SCSI Iface", "Parallel SCSI Interface", "SCSI Interface"]

   # Make a copy of the array and table
   columnDefinitions = hbaColumnDefinitions[0:]
   columnBuilders = dict(hbaColumnBuilders)

   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_PARALLEL_SCSI_INTERFACE", columnDefinitions, buildSpec)

   return tableDefinition


## Get Block SCSI table definition.
#
# Gets a table specification that can be used to create a table of Block
# SCSI hba information.
def GetBlockScsiInterface():
   rowPaths = ["Host", "Storage Info", "All SCSI Iface", "Block SCSI Interface", "SCSI Interface"]

   # Make a copy of the array and table
   columnDefinitions = hbaColumnDefinitions[0:]
   columnBuilders = dict(hbaColumnBuilders)

   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_BLOCK_SCSI_INTERFACE", columnDefinitions, buildSpec)

   return tableDefinition


## Get SerialAttached SCSI table definition.
#
# Gets a table specification that can be used to create a table of Block
# SCSI hba information.
def GetSerialAttachedScsiInterface():
   rowPaths = ["Host", "Storage Info", "All SCSI Iface", "SerialAttached SCSI Interface", "SCSI Interface"]

   # Make a copy of the array and table
   columnDefinitions = hbaColumnDefinitions[0:]
   columnBuilders = dict(hbaColumnBuilders)

   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_SERIALATTACHED_SCSI_INTERFACE", columnDefinitions, buildSpec)

   return tableDefinition


## Get Fibre Channel SCSI table definition.
#
# Gets a table specification that can be used to create a table of Fibre
# Channel hba information.
def GetFibreChannelScsiInterface():
   rowPaths = ["Host", "Storage Info", "All SCSI Iface", "FibreChannel SCSI Interface"]
   columnDefinitions = hbaColumnDefinitions + [ \
      TableColumnDefinition("LINK_STATE", None),
      TableColumnDefinition("WWPN", None),
      TableColumnDefinition("WWNN", None),
      ]

   columnBuilders = {
      "NAME": NodeAccessList(["SCSI Interface", "Name"]),
      "DRIVER": NodeAccessList(["SCSI Interface", "Driver"]),
      "IS_VIRTUAL": NodeAccessList(["SCSI Interface", "Is Virtual"]),
      "CONSOLE_NAME": NodeAccessList(["SCSI Interface", "Console Name"]),
      "QUEUE_DEPTH": NodeAccessList(["SCSI Interface", "Queue Depth"]),
      "PCI_KEY": NodeAccessListComposer( [ ["SCSI Interface", "PCI Device", "Bus"],
                                           ["SCSI Interface", "PCI Device", "Slot"],
                                           ["SCSI Interface", "PCI Device", "Function"] ],
                                         '%(SCSI Interface/PCI Device/Bus)s' + ':' +
                                         '%(SCSI Interface/PCI Device/Slot)s' + '.' +
                                         '%(SCSI Interface/PCI Device/Function)s'),
      "VENDOR_NAME": NodeAccessList(["SCSI Interface", "PCI Device", "Vendor Name"]),
      "DEVICE_NAME": NodeAccessList(["SCSI Interface", "PCI Device", "Device Name"]),
      "LINK_STATE": NodeAccess("Link State"),
      "WWPN": NodeAccess("World Wide Port Number"),
      "WWNN": NodeAccess("World Wide Node Number"),
      }
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_FIBRECHANNEL_SCSI_INTERFACE", columnDefinitions, buildSpec)

   return tableDefinition


## Get Storage Disk LUN table definition.
#
# Gets a table specification that can be used to create a table of LUN
# device information.
def GetStorageDiskLun():
   rowPaths = ["Host", "Storage Info", "All Luns", "Disk Lun"]
   columnDefinitions = [ \
      TableColumnDefinition("NAME", None),
      TableColumnDefinition("TYPE", None),
      TableColumnDefinition("VENDOR", None),
      TableColumnDefinition("MODEL", None),
      TableColumnDefinition("SIZE", None),
#      TableColumnDefinition("CONSOLE_DEVICE", None),
      TableColumnDefinition("DEVFS_PATH", None),
      TableColumnDefinition("SCSI_LEVEL", None),
      TableColumnDefinition("PSEUDO", None),
#      TableColumnDefinition("EXTERNAL_ID", None),
      ]

   columnBuilders = {
      "NAME": NodeAccessList(["LUN", "Name"]),
      "TYPE": NodeAccessList(["LUN", "Type"]),
      "VENDOR": NodeAccessList(["LUN", "Vendor"]),
      "MODEL": NodeAccessList(["LUN", "Model"]),
      "SIZE": NodeAccess("Size"),
#      "CONSOLE_DEVICE": NodeAccessList(["LUN", "Console Device"]),
      "DEVFS_PATH": NodeAccessList(["LUN", "Devfs Path"]),
      "SCSI_LEVEL": NodeAccessList(["LUN", "SCSI Level"]),
      "PSEUDO": NodeAccessList(["LUN", "Is Pseudo"]),
#      "EXTERNAL_ID": NodeAccessList(["LUN", "External Id"]),
      }
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_SCSI_DISK", columnDefinitions, buildSpec)

   return tableDefinition


## Get Storage LUN table definition.
#
# Gets a table specification that can be used to create a table of LUN
# device information.
def GetStorageLun():
   rowPaths = ["Host", "Storage Info", "All Luns", "LUN"]
   columnDefinitions = [ \
      TableColumnDefinition("NAME", None),
      TableColumnDefinition("TYPE", None),
      TableColumnDefinition("VENDOR", None),
      TableColumnDefinition("MODEL", None),
#      TableColumnDefinition("CONSOLE_DEVICE", None),
      TableColumnDefinition("DEVFS_PATH", None),
      TableColumnDefinition("SCSI_LEVEL", None),
      TableColumnDefinition("PSEUDO", None),
#      TableColumnDefinition("EXTERNAL_ID", None),
      ]

   columnBuilders = {
      "NAME": NodeAccess("Name"),
      "TYPE": NodeAccess("Type"),
      "VENDOR": NodeAccess("Vendor"),
      "MODEL": NodeAccess("Model"),
#      "CONSOLE_DEVICE": NodeAccess("Console Device"),
      "DEVFS_PATH": NodeAccess("Devfs Path"),
      "SCSI_LEVEL": NodeAccess("SCSI Level"),
      "PSEUDO": NodeAccess("Is Pseudo"),
#      "EXTERNAL_ID": NodeAccess("External Id"),
      }
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_SCSI_LUN", columnDefinitions, buildSpec)

   return tableDefinition


## Get VMFS table definition.
#
# Gets a table specification that can be used to create a table of VMFS
# volumes information.
def GetVmfs():
   rowPaths = ["Host", "Storage Info", "VMFS Filesystems", "Vm FileSystem"]
   columnDefinitions = [ \
      TableColumnDefinition("VOLUME_NAME", None),
      TableColumnDefinition("VOLUME_UUID", None),
      TableColumnDefinition("HEAD_EXTENT", None),
      TableColumnDefinition("VERSION", None),
      TableColumnDefinition("SIZE", None),
      TableColumnDefinition("USAGE", None),
      TableColumnDefinition("TOTAL_BLOCKS", None),
      TableColumnDefinition("BLOCK_SIZE", None),
      TableColumnDefinition("BLOCKS_USED", None),
      TableColumnDefinition("LOCK_MODE", None),
      TableColumnDefinition("CONSOLE_PATH", None),
      ]

   columnBuilders = {
      "VOLUME_NAME": NodeAccess("Volume Name"),
      "VOLUME_UUID": NodeAccess("Volume UUID"),
      "HEAD_EXTENT": NodeAccess("Head Extent"),
      "VERSION": NodeAccessComposer( ["Major Version", "Minor Version"],
                                     '%(Major Version)s.%(Minor Version)s'),
      "SIZE": NodeAccess("Size"),
      "USAGE": NodeAccess("Usage"),
      "TOTAL_BLOCKS": NodeAccess("Total Blocks"),
      "BLOCK_SIZE": NodeAccess("Block Size"),
      "BLOCKS_USED": NodeAccess("Blocks Used"),
      "LOCK_MODE": NodeAccess("Lock Mode"),
      "CONSOLE_PATH": NodeAccess("Console Path"),
      }
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_VMFS_VOLUME", columnDefinitions, buildSpec)

   return tableDefinition


## Get NetworkFileSystem table definition.
#
# Gets a table specification that can be used to create a table of VMFS
# volumes information.
def GetNetworkFilesystem():
   rowPaths = ["Host", "Storage Info", "Network Filesystems", "Vm FileSystem"]
   columnDefinitions = [ \
      TableColumnDefinition("VOLUME_NAME", None),
      TableColumnDefinition("VOLUME_UUID", None),
      TableColumnDefinition("HOSTNAME", None),
      TableColumnDefinition("IP_ADDRESS", None),
      TableColumnDefinition("SHARE", None),
      TableColumnDefinition("HEAD_EXTENT", None),
      TableColumnDefinition("SIZE", None),
      TableColumnDefinition("USAGE", None),
      TableColumnDefinition("TOTAL_BLOCKS", None),
      TableColumnDefinition("BLOCK_SIZE", None),
      TableColumnDefinition("BLOCKS_USED", None),
      TableColumnDefinition("MOUNTED", None),
      TableColumnDefinition("READONLY", None),
      TableColumnDefinition("ACCESSIBLE", None),
      TableColumnDefinition("CONSOLE_PATH", None),
      ]

   columnBuilders = {
      "VOLUME_NAME": NodeAccess("Volume Name"),
      "VOLUME_UUID": NodeAccess("Volume UUID"),
      "HOSTNAME": NodeAccess("Host"),
      "IP_ADDRESS": NodeAccess("IP Addr"),
      "SHARE": NodeAccess("Share"),
      "HEAD_EXTENT": NodeAccess("Head Extent"),
      "SIZE": NodeAccess("Size"),
      "USAGE": NodeAccess("Usage"),
      "TOTAL_BLOCKS": NodeAccess("Total Blocks"),
      "BLOCK_SIZE": NodeAccess("Block Size"),
      "BLOCKS_USED": NodeAccess("Blocks Used"),
      "MOUNTED": NodeAccess("Mounted"),
      "READONLY": NodeAccess("ReadOnly"),
      "ACCESSIBLE": NodeAccess("Accessible"),
      "CONSOLE_PATH": NodeAccess("Console Path"),
      }
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_NETWORK_VOLUME", columnDefinitions, buildSpec)

   return tableDefinition


## Get Loaded Module table definition.
#
# Gets a table specification that can be used to create a table of VMFS
# volumes information.
def GetLoadedModule():
   rowPaths = ["Host", "System Info", "Loaded Modules", "Module"]
   columnDefinitions = [ \
      TableColumnDefinition("NAME", None),
      TableColumnDefinition("FILENAME", None),
      TableColumnDefinition("VERSION", None),
      TableColumnDefinition("LOADED", None),
      TableColumnDefinition("ENABLED", None),
      TableColumnDefinition("USE_COUNT", None),
      TableColumnDefinition("OPTIONS", None),
      ]

   columnBuilders = {
      "NAME": NodeAccess("Name"),
      "FILENAME": NodeAccess("File Name"),
      "VERSION": NodeAccess("Version"),
      "LOADED": NodeAccess("Loaded"),
      "ENABLED": NodeAccess("Enabled"),
      "USE_COUNT": NodeAccess("Use Count"),
      "OPTIONS": NodeAccess("Options"),
      }
   buildSpec = TableBuildSpec(rowPaths, columnBuilders)

   tableDefinition = TableDefinition("ESXCFG_LOADED_MODULE", columnDefinitions, buildSpec)

   return tableDefinition


## Get all table definitions.
def GetAll():
   tableDefinitions = [
      GetCpu(),
      GetPciDevice(),
      GetPhysicalNic(),
      GetVmkernelNic(),
      GetVirtualSwitch(),
      GetPortGroup(),
      GetBlockIdeInterface(),
      GetParallelScsiInterface(),
      GetBlockScsiInterface(),
      GetSerialAttachedScsiInterface(),
      GetFibreChannelScsiInterface(),
      GetStorageDiskLun(),
      GetStorageLun(),
      GetVmfs(),
      GetNetworkFilesystem(),
      GetLoadedModule(),
      ]
   return tableDefinitions
