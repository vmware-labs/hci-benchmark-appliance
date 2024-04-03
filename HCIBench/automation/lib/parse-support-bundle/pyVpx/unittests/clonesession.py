import sys
import time
from pyVmomi import Vim, SoapStubAdapter
from pyVim import arguments
from pyVim import folder, vm
from pyVim.helpers import Log

supportedArgs = [ (["t:", "ticket="], "", "ticket", "ticket") ]
supportedToggles = [ (["usage", "help"], False, "usage information", "usage") ]
args = arguments.Arguments(sys.argv, supportedArgs, supportedToggles)

if args.GetKeyValue("usage") == True:
   args.Usage()
   sys.exit(0)

ticket = args.GetKeyValue("ticket")
host = 'localhost'
stub = SoapStubAdapter(host=host, version="vim.version.version10")
newsi = Vim.ServiceInstance("ServiceInstance", stub)

# Try to acquire a clone ticket on a un-authenticated session. Should fail.
try:
   newsi.GetContent().GetSessionManager().AcquireCloneTicket()
except:
   pass

newsm = newsi.GetContent().GetSessionManager().CloneSession(ticket)
for vm1 in folder.GetVmAll(si=newsi):
   print vm1

try:
   Log("Power Off (should pass)")
   vm1.PowerOff()
   time.sleep(5)
   Log("pass\n")
except Exception, e:
   print Exception, e
   Log("fail\n")
   pass

try:
   Log("Power On (should pass)")
   vm1.PowerOn()
   time.sleep(5)
   Log("pass\n")
except Exception, e:
   print Exception, e
   Log("fail\n")
   pass

try:
   Log("Acquiring MKS Ticket(should pass)")
   vm1.AcquireMksTicket()
   time.sleep(2)
   Log("pass\n")
except Exception, e:
   print Exception, e
   Log("fail\n")
   pass

try:
   Log("Trying to query unowned files(should taise NoPermission)")
   vm1.QueryUnownedFiles()
   time.sleep(2)
   Log("fail\n")
except Exception, e:
   time.sleep(2)
   print Exception, e
   Log("pass\n")
   pass

time.sleep(2)
Log("Logging out")
newsi.GetContent().GetSessionManager().Logout()

