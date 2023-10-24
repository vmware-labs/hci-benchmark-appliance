#!/usr/bin/python

from __future__ import print_function

import sys
from pyVmomi import Vim, Hostd
from pyVmomi import VmomiSupport
from pyVim.connect import SmartConnect, Disconnect, GetStub
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import arguments
import atexit

def GetStatList(reg, display=True):
   stats = reg.QueryStatList()

   if not display:
      return stats

   #display all stats in details
   print('============stats supported by the host===========')
   for stat in stats:
      statId = stat.GetId()
      statDef = stat.GetStatDef()
      print('stat id: %s name: %s' % (statId, statDef.GetName()))
      for statAttr in statDef.GetAttribute():
         print('      statAttr name: %s, type: %s, wildCard: %s'
               % (statAttr.GetName(), statAttr.GetType(),
                  statAttr.GetWildCardAllowed()))

   return stats

def GetStatValue(reg, stats, display=True):
   print("===========stat instance input===========")
   statInstances = Hostd.StatsRegistryManager.StatInstance.Array()
   for stat in stats:
      statId = stat[0]
      attrValues = None
      if len(stat) > 1:
         attrValues = stat[1:]
      statInstance = Hostd.StatsRegistryManager.StatInstance()
      statInstance.SetId(statId)
      statInstance.SetAttrValue(attrValues)
      print(GetStatInstanceString(statInstance))
      statInstances.append(statInstance)

   statValues = reg.QueryStatValue(statInstances)
   if not display:
      return statValues

   print("===========stat instance values output ===========")
   #print returned stat values
   for statValue in statValues:
      statStr = GetStatInstanceString(statValue.GetInstance())
      statStr = statStr + '   Stat Value: ' + str(statValue.GetValue())
      print(statStr)

   return statValues

def GetStatInstanceString(statInstance):
   statStr = str(statInstance.GetId()) + ':'
   if statInstance.GetAttrValue() is None:
      return statStr
   for attrValue in statInstance.GetAttrValue():
      statStr = statStr + ' "' + attrValue + '"'
   return statStr

def GetRegistry(hostIn="localhost", userIn="root", pwdIn="ca$hc0w"):
   # Connect
   si = SmartConnect(host=hostIn,
                     user=userIn,
                     pwd=pwdIn)
   atexit.register(Disconnect, si)

   stub = GetStub()
   registry = Hostd.StatsRegistryManager('ha-internalsvc-statsregistrymgr', stub)
   if registry is None:
      print('failed to get stats registry object')

   return registry

def main():
   supportedArgs = [ (["h:", "host="], "localhost", "Host name", "host"),
                     (["u:", "user="], "root", "User name", "user"),
                     (["p:", "pwd="], "ca$hc0w", "Password", "pwd")]

   supportedToggles = [ (["usage", "help"], False, "Show usage information", "usage") ]

   args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)
   if args.GetKeyValue("usage") == True:
      args.Usage()
      sys.exit(0)

   reg = GetRegistry(args.GetKeyValue("host"),
                args.GetKeyValue("user"),
                args.GetKeyValue("pwd"))
   if reg == None:
      print("Stats registry instance is NULL!")
      sys.exit(0)

   #get supported stats definition
   stats = GetStatList(reg)
   print(stats)

   #get stat value
   statValues = GetStatValue(reg, [[1], [2, '1']])

# Start program
if __name__ == "__main__":
    main()
