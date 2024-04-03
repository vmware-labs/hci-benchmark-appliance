#
# pyHbr.opid.py
#
# Utility to make setting OpIds easier.
#

import random

from pyVmomi import VmomiSupport

def SetOpId(opId = None, prefix = None, show = False):
   '''
   Set/Generate the opID that will show up in the logs of remote VMODL calls.
   '''
   # If no opId is supplied, generate a new one
   if not opId:
      opId = "%x" % random.randint(0,(2**32)-1)
   
   if prefix:
      opId = prefix + opId
   
   if show:
      print("Using opId: %s" % opId)
   
   reqCtx = VmomiSupport.GetRequestContext()
   reqCtx["operationID"]=opId
