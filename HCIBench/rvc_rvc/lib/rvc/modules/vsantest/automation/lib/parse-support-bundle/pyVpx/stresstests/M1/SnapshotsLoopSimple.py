"""Repeatedly perform VM snapshot creation and deletion on a specific VM.

Usage: create_delete_loop.py [options]

Options:
    -h / --help
        Print this message and exit.

    -H hostname
    --hostname=hostname
        The hostname (required field)

    -v vmname
    --vmname=vmname
        Name of the vm to use for testing (required field)

    -i number of iterations
        Number of iterations to run the test for (default is 1)
        
"""
import sys
import getopt
import time
from pyVmomi import Vim
from pyVim.connect import Connect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm
from pyVim import vimutil

def usage(msg=''):
    print >> sys.stderr, __doc__
    if msg:
        print >> sys.stderr, msg

def now():
    return time.strftime("%a, %d %b %Y %H:%M:%S %p", time.localtime())

def GetVmByName(vmname):
    vmList = folder.GetAll()
    print vmList
    for vmIter in vmList:
        if (vmIter.GetName() == vmname):
            return vmIter
        
    return None
         
def main():
    # Process command line
    try:
        opts, args = getopt.getopt(sys.argv[1:],"hH:v:i:",["help","hostname=","vmname="])
    except getopt.error, msg:
        # print help information and return:
        usage(msg)
        return(1)
    host = None
    vmName = None
    numIterations = 1
    for opt, arg in opts:
        if opt in ("-h","--help"):
            usage()
            return(0)
        
        if opt in ("-H","--hostname"):
            host = arg
            
        if opt in ("-v","--vmname"):
            vmName = arg

        if opt in ("-i"):
            numIterations = int(arg)

    if host == None or vmName == None:
       usage()
       return(1)

    # Connect
    si = Connect(host)

    # Get the vm
    vm = GetVmByName(vmName)
    if vm == None:
       print "Unable to find VM", vmName
       return(1)   

    task = vm.PowerOn(None);
    WaitForTask(task)
    
    print "Test started on ", now()
    # Get vms
    for i in xrange(0, numIterations):
        print "== iteration ", str(i+1), " time = ", now()
        print "Creating Snapshot"
        task = vm.CreateSnapshot("testSnapshot", "M1 stress test snapshot", False, False)
        WaitForTask(task)

        snapshot = vm.GetSnapshot()
        
        print "Deleting Snapshot ", vmName
        task = snapshot.GetCurrentSnapshot().Remove(True)
        WaitForTask(task)        
   
        print "== iteration completed ", str(i+1), " time = ", now()

    print "## Total number of iterations performed ", str(i+1)

    task = vm.PowerOff();
    WaitForTask(task)
    return(0)

# Start program
if __name__ == "__main__":
    retval = main()
    print "Test ended with error code ", str(retval), " on ", now()
    sys.exit(retval)
