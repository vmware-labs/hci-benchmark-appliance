#!/usr/bin/python

from __future__ import print_function

from pyVmomi import VmomiSupport, Vmodl, Vim

def TestPrimitiveAny():
   dynamicProperty = Vim.DynamicProperty()
   dynamicProperty.SetName("primitive name")
   dynamicProperty.SetVal(VmomiSupport.PrimitiveString("foobar"))

   print(dynamicProperty)

def TestDataObjectAny():
   capability = Vim.Capability()
   capability.SetProvisioningSupported(True)
   capability.SetMultiHostSupported(True)

   dynamicProperty = Vim.DynamicProperty()
   dynamicProperty.SetName("data object name")
   dynamicProperty.SetVal(capability)

   print(dynamicProperty)

def TestNullAny():
   change = Vmodl.Query.PropertyCollector.Change()
   change.SetName("content")
   change.SetOp("add")
   change.SetVal(None)

   print(change)

def main():
   """
   # Test the serialization and deserialization of Any objects.  If the test
   # code runs without any errors, then it's working.
   """
   TestPrimitiveAny()
   TestDataObjectAny()
   TestNullAny()

# Start program
if __name__ == "__main__":
   main()
