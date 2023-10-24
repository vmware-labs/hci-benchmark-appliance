"""Repeatedly power on and power off VMs on a specific host

Usage: ./PowerOnPowerOffSimple.py [options]

Options:
    -h / --help
        Print this message and exit.

    -H hostname
    --hostname=hostname
        The hostname (required field)

    -k / --skip
    --skip=[1 | 0]
        skip every other VM if skip == 1

    -s / --start
    --start=vm_index
        index of the VM in the folder list to start power ops from
"""
import sys
import getopt
import time
from pyVmomi import Vim
from pyVim.connect import Connect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm

def usage(msg=''):
    print >> sys.stderr, __doc__
    if msg:
        print >> sys.stderr, msg

def now():
    return time.strftime("%a, %d %b %Y %H:%M:%S %p", time.localtime())

def main():
    # Process command line
    try:
        opts, args = getopt.getopt(sys.argv[1:],"hH:k:s:",["help","hostname=","skip=","start="])
    except getopt.error, msg:
        # print help information and return:
        usage(msg)
        return(1)
    host = None
    start = None
    skip = None
    for opt, arg in opts:

        if opt in ("-h","--help"):
            usage()
            return(0)
        
        if opt in ("-H","--hostname"):
            host = arg

        if opt in ("-k","--skip"):
            skip = arg

        if opt in ("-s","--start"):
            start = arg
            
    if host == None:
       usage()
       return(1)

    # Connect
    si = Connect(host)

    print "Test started on ", now()
    vms = folder.GetAll()
    start_time = time.time()

    i = 0
    if start == None:
       start = 0;

    # Get vms
    while (time.time() - start_time) < (60*60*2): # 2 hours 
        print "== iteration ", str(i+1), " time = ", now()

        skip_next = False
        for index in range(int(start), len(vms)):
           if skip != None and skip_next:
              skip_next = False
              continue

           vmIter = vms[index]
           print "  powering on ", vmIter.GetName()
           vm.PowerOn(vmIter)
           print "  powering off ", vmIter.GetName()
           vm.PowerOff(vmIter)
           skip_next = True

        print "== iteration completed ", str(i+1), " time = ", now()
        i = i + 1

    print "## Total number of iterations performed ", str(i)
    return(0)

# Start program
if __name__ == "__main__":
    retval = main()
    print "Test ended with error code ", str(retval), " on ", now()
    sys.exit(retval)
