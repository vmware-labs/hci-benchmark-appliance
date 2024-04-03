#!/usr/bin/python

"""
Simple command-line program for dumping the host config.
"""
from __future__ import print_function

from pyVim.connect import Connect
from pyVim import host
from optparse import OptionParser
from pyVmomi import Vim


def GetOptions():
   """
   Supports the command-line arguments listed below.
   """

   parser = OptionParser()
   parser.add_option("--host",
                     default="localhost",
                     help="remote host to connect to")
   parser.add_option("-u", "--user",
                     default="root",
                     help="User name to use when connecting to hostd")
   parser.add_option("-p", "--password", "--pwd",
                     default="ca$hc0w",
                     help="Password to use when connecting to hostd")
   (options, _) = parser.parse_args()
   return options

def main():
   """
   Simple command-line program for dumping the host config.
   """

   options = GetOptions()

   serviceInstance = Connect(host=options.host,
                             user=options.user,
                             pwd=options.password)

   content = serviceInstance.RetrieveContent()
   dataCenter = content.GetRootFolder().GetChildEntity()[0]
   hostFolder = dataCenter.GetHostFolder()
   computeResource = hostFolder.GetChildEntity()[0]
   hostSystem = computeResource.GetHost()[0]

   hostConfigManager = hostSystem.GetConfigManager()
   print(hostConfigManager)

   optManager = hostConfigManager.GetAdvancedOption()
   print(optManager)

   optionValue = []
   optionValue = optManager.QueryView("RdmFilter.HbaIsShared")
   print("Get OptionValue ")
   print(optionValue)

   print("Now setting the value to true")
   allOptions = []
   opt = Vim.Option.OptionValue()
   opt.SetKey("RdmFilter.HbaIsShared")
   opt.SetValue(True)
   allOptions.append(opt)
   optManager.UpdateValues(allOptions)

   print("validate that value get set to true")
   optionValue = optManager.QueryView("RdmFilter.HbaIsShared")
   print("Get OptionValue ")
   print(optionValue)

   print("Now setting the value to false")
   allOptions = []
   opt = Vim.Option.OptionValue()
   opt.SetKey("RdmFilter.HbaIsShared")
   opt.SetValue(False)
   allOptions.append(opt)
   optManager.UpdateValues(allOptions)

   print("validate that value get set to false")
   optionValue = optManager.QueryView("RdmFilter.HbaIsShared")
   print("Get OptionValue ")
   print(optionValue)


# Start program
if __name__ == "__main__":
   main()
