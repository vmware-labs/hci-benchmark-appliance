""" Multi-threaded test that runs create/delete, poweron/off/,
    and createsnapshot/deletesnapshot in concurrent pairs such that
    one op succeeds while the other fails. 

Usage: concurrent-stress.py [options]

Options:
    -h / --help
        Print this message and exit.
    
    -o operation
    --operation=operation
	The operation to be performed which can be one of either
	create, powerop, or snapshot (default is create)

    -H hostname
    --hostname=hostname
        The hostname (required field)

    -v vmname
    --vmname=vmname
        Name of the vm to use for testing (required field)

    -i number of iterations
        Number of iterations to run the test for. If this value
        is omitted, the test will run for two hours.
        
"""

import sys
import threading
import getopt
import time
from pyVmomi import Vim
from pyVim.connect import Connect
from pyVim.task import WaitForTask
from pyVim import folder
from pyVim import vm

_op = "create"
_vmName = None
_host = None
_taskComplete = threading.Condition()
_taskCount = 0
_testStartTime = time.time()

def usage(msg=''):
    print >> sys.stderr, __doc__
    if msg:
        print >> sys.stderr, msg

def now():
    return time.strftime("%a, %d %b %Y %H:%M:%S %p", time.localtime())

"""
Class RunOp begins here
"""

class RunOp(threading.Thread):
    def __init__(self, id):
        self.id = id
	self.toggle = "on"
	self.status = "incomplete"
        threading.Thread.__init__(self)
        
    def RunToggleOp(self):
	ret = 0
	global _op
        if _op == "create":
	    if self.id == 1 and self.toggle == "on":
		self.status = "fail"
		return
            ret = ToggleCreate(self.toggle)
    	elif _op == "powerop":
	    ret = TogglePowerOp(self.toggle)
    	else:
	    ret = ToggleSnapshot(self.toggle)	
	if ret == 0:
	    self.status = "pass"
	else:
	    self.status = "fail"
	

    def CompleteOp(self):
	global _taskCount
	_taskComplete.acquire()
	_taskCount = _taskCount + 1
	print "== Client ", str(self.id)," waiting after completion ", \
	      "Op status = ", str(self.status)
	_taskComplete.wait()
	_taskComplete.release()


    def run(self):
	si = Connect(_host)
	print "== Client ", str(self.id), " connected to host"
	while(1): 
	    try:
	       if self.status == "kill":
		    break
	       print "== Client ", str(self.id), " running operation Toggle", str(self.toggle)
	       self.RunToggleOp()
	    except Exception, e:
	       print "Failed test due to exception:", str(e)
	       self.status = "fail"
	    self.CompleteOp()
	

"""
Class RunOp ends here
"""


def GetVmByName(vmname):
    """ Get a given VM by name """
    vmList = folder.GetAll()
    for vmIter in vmList:
        if (vmIter.GetName() == vmname):
            return vmIter       
    return None

def ToggleSnapshot(toggle):
    """ Create/Remove Snapshots on a given VM """
    vm = GetVmByName(_vmName)
    if vm == None:
       print "Unable to find VM", _vmName
       return(1)   

    if toggle == "on":
	print "== Creating Snapshot"
	task = vm.CreateSnapshot("testSnapshot", "M3 stress test snapshot", False, False)
	if WaitForTask(task) == "error":
	    return(1)
	return(0)	
    else:
	print "== Deleting Snapshot"
	snapshot = vm.GetSnapshot()
	task = snapshot.GetCurrentSnapshot().Remove(True)
        if WaitForTask(task) == "error":
	    return(1)
	return(0)

def TogglePowerOp(toggle):
    """ Power On/Off a given VM """
    vm = GetVmByName(_vmName)
    if vm == None:
       print "Unable to find VM", _vmName
       return(1)   

    if toggle == "on":
	print "== Powering On VM"
	task = vm.PowerOn(None)
	if WaitForTask(task) == "error":
	    return(1)
	return(0)	
    else:
	print "== Powering Off VM"
	task = vm.PowerOff()
        if WaitForTask(task) == "error":
	    return(1)
	return(0)

def ToggleCreate(toggle):
    """ Create/Delete a given VM """
    if toggle == "on":
	print "== Creating VM"
	vmTemp = vm.CreateQuickDummy(_vmName, 1)
 	if vmTemp == None:
           print "Error in creating: ", _vmName
           return(1)
	return(0)
    else:
        print "== Deleting VM"
        vm1 = GetVmByName(_vmName)
    	if vm1 == None:
       	   print "Unable to find VM", _vmName
       	   return(1)   
	task = vm1.Destroy()
        if WaitForTask(task) == "error":
	    return(1)
	return(0)

def CheckStatus(threads):
    """ Check the status of two simulatenous tests """
    if (threads[0].status == "pass" and threads[1].status == "fail") or (
        threads[0].status == "fail" and threads[1].status == "pass"):
	print "== Task successful"
	for t in threads:
	    t.status = "incomplete"
	    if t.toggle == "on":
		t.toggle = "off"
	    else:
		t.toggle = "on"
	return 0
    print "== Task failed"
    return 1	    

def WaitForCompletion(threads):
    """ Kill all clients  """
    for t in threads:
	t.status = "kill"
    _taskComplete.notifyAll()
    _taskComplete.release()


def main():
    """ Program execution begins here """
    # Process command line
    try:
        opts, args = getopt.getopt(sys.argv[1:],"ho:H:v:i:",[
	"help","operation=","hostname=","vmname="])
    except getopt.error, msg:
        # print help information and return:
        usage(msg)
        return(1)
    numIterations = 0
    global _host
    global _vmName
    global _op
    for opt, arg in opts:
        if opt in ("-h","--help"):
            usage()
            return(0)
        
        if opt in ("-o","--operation"):
            _op = arg

        if opt in ("-H","--hostname"):
            _host = arg
            
        if opt in ("-v","--vmname"):
            _vmName = arg
	
	if opt in ("-i"):	
            numIterations = int(arg)

    if _host == None or _vmName == None:
       usage()
       return(1)
    
    # Create the threads
    threads = []
    t1 = RunOp(1)
    t2 = RunOp(2)
    print "Test started on ", now()	
    threads.append(t1)
    threads.append(t2)

    print "## Test start time: ", now()	
    startTime = time.time()
 
    # Run each operation 
    for t in threads:
	t.start()

    # Wait for both threads to complete each iteration
    i = 1
    global _taskCount
    while(1):	
        _taskComplete.acquire()
	if _taskCount == 2:
	    print "== iteration ", str(i), " completed for Toggle", \
	    str(threads[0].toggle), " at time ", now() 
	    if CheckStatus(threads) == 0:
		_taskCount = 0
		i = i+1
		if numIterations > 0: 
		   if i > numIterations*2:
		       break
		elif (time.time() - startTime) >= (60*60*2): # 2 hours
		   break	
		_taskComplete.notifyAll()
		_taskComplete.release()
	    else:
		print "== Tests failed to synchronize result status"
		break
	elif _taskCount > 2:
	   print "Error: Task count invalid"
	   break
	else:
	   _taskComplete.release()
	   time.sleep(2)
    
    WaitForCompletion(threads)	
    print "## Test completion time: ", now()		
    print "## Total number of iterations performed ", str(i/2)
    return(0)

# Start program
if __name__ == "__main__":
    main()

       
