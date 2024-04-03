"""Repeatedly perform VM creation and deletion on a specific host

Usage: create_delete_loop.py [options]

Options:
    -h / --help
        Print this message and exit.

    -H hostname
    --hostname=hostname
        The hostname (required field)

    -t temporary_vm_name
    --tempvmname=temporary_vm_name
        The temporary VM name (required field)
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
        opts, args = getopt.getopt(sys.argv[1:],"hH:t:",["help","hostname=","tempvmname="])
    except getopt.error, msg:
        # print help information and return:
        usage(msg)
        return(1)
    host = None
    tempVmName = None
    for opt, arg in opts:
        if opt in ("-h","--help"):
            usage()
            return(0)
        
        if opt in ("-H","--hostname"):
            host = arg
            
        if opt in ("-t","--tempvmname"):
            tempVmName = arg

    if host == None or tempVmName == None:
       usage()
       return(1)

    # Connect
    si = Connect(host)

    start_time = time.time()
    i = 0
    print "Test started on ", now()
    # Get vms
    while (time.time() - start_time) < (60*60*2): # 2 hours
        print "== iteration ", str(i+1), " time = ", now()
        print "  Creating: ", tempVmName
        vmTemp = vm.CreateQuickDummy(tempVmName,1)
        if vmTemp == None:
            print "** Error in creating: ",tempVmName
            return(2)

        print "  Deleting: ", tempVmName
        task = vmTemp.Destroy()
        WaitForTask(task)

        vmTemp = folder.Find(tempVmName)
        if vmTemp != None:
            print "** Deleted Vm still present: ", tempVmName
            return(3)
            
        print "== iteration completed ", str(i+1)
        i = i + 1

    print "## Total number of iterations performed ", str(i)
    return(0)

# Start program
if __name__ == "__main__":
    retval = main()
    print "Test ended with error code ", str(retval), " on ", now()
    sys.exit(retval)
