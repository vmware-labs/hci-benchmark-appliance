#!/usr/bin/python

###
### Test description:
###
### Create/Delete stress test. Creates/poweron/off/unregister/register/deletes on two threads
###

from __future__ import print_function

import sys
from pyVmomi import Vim
from pyVmomi import VmomiSupport
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm
import threading
import time
import atexit

class RunCreate(threading.Thread):
    def __init__(self, id):
        self.id = id
        threading.Thread.__init__(self)

    def run(self):
        try:
	   for x in range(1,20):
	      RunCreateTest("Bizzaro-Land-Stress-" + str(self.id))
	except Exception as e:
	   print("Failed test due to exception: %s" % e)
	   raise


def RunCreateTest(name):
    vm1 = vm.CreateQuickDummy(name)
    vm.PowerOn(vm1)
    vm.PowerOff(vm1)
    cfgPath = vm1.GetConfig().GetFiles().GetVmPathName()
    vm1.Unregister()
    folder.Register(cfgPath)
    vm.Destroy(vm1)

def main():
    # Process command line
    host = "jairam-esx"
    if len(sys.argv) > 1:
       host = sys.argv[1]

    # Connect
    try:
       si = Connect(host)
       atexit.register(Disconnect, si)

       for i in range(1, 10):
	   print("Launching create thread %s" % i)
	   RunCreate(i).start()

       while 1:
           time.sleep(2)

    except Exception as e:
	print("Failed test due to exception: %s" % e)


# Start program
if __name__ == "__main__":
    main()


