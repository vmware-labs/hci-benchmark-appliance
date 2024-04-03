#!/usr/bin/python

from pyVmomi import SoapStubAdapter, Vmodl, Vim
import pyVim.vimApiTypeMatrix
import pyVim.vimApiGraph

def connect(host, port, user, pwd, adapter="SOAP"):
   if adapter == None:
      adapter = "SOAP"

   if host == None:
      host = "localhost"

   if port == None:
      port = 443

   if user == None:
      user = os.getlogin()

   print "Connecting to :", host, "at", port, "as", user, "over", adapter

   # Create the VMDB stub adapter
   stub = SoapStubAdapter(host, port)

   # Get Service instance
   si = Vim.ServiceInstance("ServiceInstance", stub)
   content = si.RetrieveContent()
   sessionManager = content.GetSessionManager()

   # Login locally
   if pwd == None:
      localTicket = sessionManager.AcquireLocalTicket(user)
      user = localTicket.GetUserName()
      passwordFile = localTicket.GetPasswordFilePath()
      try:
         fd = open(passwordFile, "r")
         pwd = fd.readline()
         fd.close()
      except Exception:
         msg = "Failed to read password file.  A password is required to " + \
               "connect remotely."
         raise Exception(msg)
      
   # Login
   try:
      x = sessionManager.Login(user, pwd, None);
   except Vim.Fault.InvalidLogin:
      print "Invalid login:", user	
   except:
      print "Failed to login as ", user
      sys.exit()

   return si



# GetServiceInstance
def GetServiceInstance(host, port, user, password, adapter):
   # Connect
   si = None
   try:
      si = connect(host, port, user, password, adapter)
   except Exception, e:
      print e
      sys.exit(2)

   return si

# Get PropertyCollector from ServiceInstance
def GetPropertyCollector(si):
   content = si.RetrieveContent()
   pc = content.GetPropertyCollector()
   return pc

def SortByManagedObject(x, y):
   x = x.GetObj()
   y = y.GetObj()
   result = cmp(x._GetType(), y._GetType())
   if (result == 0):
      result = cmp(x._GetMoId(), y._GetMoId())
   return result

# [(moType, all), (moType, all), ...]
def MakePropertySpecs(managedObjectSpecs):
   propertySpecs = []

   for managedObjectSpec in managedObjectSpecs:
      moType = managedObjectSpec[0]
      all = managedObjectSpec[1]

      propertySpec = Vmodl.Query.PropertyCollector.PropertySpec()
      propertySpec.SetType(moType)
      propertySpec.SetAll(all)

      propertySpecs.append(propertySpec)

   return propertySpecs

# Use a property collector query to retrieve a list of managed objects
def GetEntities(si):
   pc = GetPropertyCollector(si)

   objectSpec = Vmodl.Query.PropertyCollector.ObjectSpec()
   objectSpec.SetObj(si)
   objectSpec.SetSkip(False)
   objectSpec.SetSelectSet(pyVim.vimApiGraph.BuildMoGraphSelectionSpec())

   fetchProp = False

   # Build up a property spec that consists of all managed object types
   matrix = pyVim.vimApiTypeMatrix.CreateMoTypeMatrix()
   classNames = matrix.GetClassNames()
   propertySpecs = map(lambda x: [x, fetchProp], classNames)
   propertySpecs = MakePropertySpecs(propertySpecs)

   objectSpecs = [objectSpec]
    
   filterSpec = Vmodl.Query.PropertyCollector.FilterSpec()
   filterSpec.SetPropSet(propertySpecs)
   filterSpec.SetObjectSet(objectSpecs)

   filterSpecs = [filterSpec]

#   print "Constructed property collector FilterSpec:"
#   print filterSpecs

   objectContents = pc.RetrieveContents(filterSpecs);
   objectContents.sort(lambda x, y: SortByManagedObject(x, y))

   entities = map(lambda x: x.GetObj(), objectContents)
   return entities

