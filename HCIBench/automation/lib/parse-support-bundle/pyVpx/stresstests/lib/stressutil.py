#!/usr/bin/env python
'''
Utilities for stress testing
'''
from optparse import OptionParser

from stresstest import LoopLimit


def splitList(list, numPieces):
   """
   Split a list into specified number of pieces.
   If the list cannot be divided into equal parts, then the remainder is
   distributed across the first pieces: if the remainder is r, then the first
   r pieces will have 1 more element than the rest of the pieces.
   Throws a ValueError when the list is to divide is smaller than the number
   of pieces specified
   """
   listlen = len(list)
   if(listlen < numPieces): raise ValueError("list length is smaller than"
                                             " number of pieces")
   newseq = []
   div, mod = divmod(listlen, numPieces)
   currpos = 0
   for pos in xrange(numPieces):
      nextpos = currpos + div + (mod > pos)
      newseq.append(list[currpos : nextpos])
      currpos = nextpos
   return newseq

def processLoopArgs():
   """
   Obtain host name,  number of clients and loop limit from the command line
   arguments. Returns 3 values: host name (string), number of clients (int)
   and loop limit (of the type stresstest.LoopLimit)
   """
   usage = "%prog [options] hostname"
   parser = OptionParser(usage=usage)
   parser.add_option("-c", "--numclients", type="int", dest="numclients"
                     , default=1
                     , help="Number of clients, or conflicting pairs of"
                     " clients [default: %default]"
                     )
   parser.add_option("-i", "--iterations", type="int", dest="iterations"
                     , default=1
                     , help="Number of iterations/loops [default: 1]"
                     )
   parser.add_option("-t", "--time", type="float", dest="time"
                     , help="Time in seconds to loop for [not enabled by"
                     " default]. If time is specified and iterations are also"
                     " specified, then looping will end whenever either limit"
                     " is reached. Note that time checking is done only at the"
                     " end of loops; clients are never terminated in the "
                     " middle of loops,even if their run time is exceeded"
                     )
   options, args = parser.parse_args()
   host = ""
   numClients = options.numclients
   loopIter = None
   loopTime = None
   if(len(args) != 1
      or (options.time != None and options.iterations != None)):
      parser.print_help()
      raise ValueError("invalid arguments")
   else:
      host = args[0]
      loopIter = options.iterations
      loopTime = options.time

   return host, numClients, LoopLimit(loopIter, loopTime)

if __name__ == "__main__":
   """
   Testing code for splitList
   """
   print splitList([0,1,2],1)
   print splitList([0,1,2],2)
   print splitList([0,1,2],3)
   print splitList([0,1,2,3,4],2)
   print splitList([0,1,2,3,4,5,6,7,8],3)
   print splitList([0,1,2,3,4,5,6,7,8,9,10],3)
