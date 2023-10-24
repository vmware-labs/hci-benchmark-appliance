#!/usr/bin/python

###
### Look for all stuck vms and answer them with a default answer
###
from __future__ import print_function

import sys
from pyVmomi import Vim
from pyVmomi import VmomiSupport
from pyVim.connect import Connect, Disconnect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm
import atexit

def main():
    # Process command line
    host = "jairam-esx"
    if len(sys.argv) > 1:
       host = sys.argv[1]

    si = Connect(host)
    atexit.register(Disconnect, si)
    vms = folder.GetAll()
    for vm in vms:
	question = vm.GetRuntime().GetQuestion()
	if question != None:
	   print("Question found on vm %s:" % vm.GetConfig().GetName())
	   print(question)
	   print("Answering with default choice")
	   vm.Answer(question.GetId(), question.GetChoice().GetChoiceInfo()[question.GetChoice().GetDefaultIndex()].GetKey())



# Start program
if __name__ == "__main__":
    main()
