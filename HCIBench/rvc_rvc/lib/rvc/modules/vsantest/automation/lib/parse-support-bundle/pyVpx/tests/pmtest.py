#
# pmtest.py
#
# Pat & Matt's test infrastructure
#

import subprocess
import sys
from pyVmomi import Vmodl # for the exceptions
from pyVim.helpers import Log


class TestFunc(object):
   """Decorator for tagging test functions.  (Look for @TestFunc)"""
   def __init__(self, f):
      self.f = f

   def __call__(self, *args):
      doc = self.f.__name__
      Log("Starting: %s" % doc)
      self.f(*args)
      Log("%s: passed" % self.f.__name__)
      Log("---")

  
class TestFailedExc(Exception):
   """Exception tests should throw when they fail."""
   def __init__(self, msg):
      self.msg = msg

   def __str__(self):
      return self.msg


def ExpectCond(cond, msg):
   """A helper function that fails a test if a condition doesn't check out"""

   if not cond:
      raise TestFailedExc(msg)


def ExpectedException(expectedType):
   """A helper function for expecting a specific type of exception."""
   (curType, curObj, curStack) = sys.exc_info();
   if curType == expectedType:
      Log("Got expected exception " +str(curObj))
   else:
      Log("Unexpected Exception: " + str(curType))
      Log("Got: " + str(curObj))

      if expectedType != None:
         Log("Expected instance of : " + str(expectedType))
         expectingMsg = str(expectedType)
      else:
         Log("Expected no exception.")
         expectingMsg = "no exception"

      raise TestFailedExc("Got unexpected exception "
                          +str(curType)+
                          ", expecting " +expectingMsg)


def ExpectException(expectedException,
                    callable, *args, **kwargs):
   """Helper function that invokes given callable with the given args and
   expects the given exception to be thrown.  Exception may be None, in
   which case any thrown exception is a failure.  Returns the callable's
   return value."""
   rv = None
   try:
      rv = callable(*args, **kwargs)
   except:
      ExpectedException(expectedException)
   else:
      if expectedException != None:
         raise TestFailedExc("No exception was thrown!  Expecting " +
                             str(expectedException) +
                             " (returned '" +str(rv)+ "')")
   return rv


def ExpectNoException(callable, *args, **kwargs):
   """Helper function that invokes the given callable and expects no
   exceptions to be thrown."""

   return ExpectException(None, callable, *args, **kwargs)


def ExpectNotImplemented(callable, *args, **kwargs):
   """Helper function that invokes the given callable and expects it
   to throw the standard not-implemented exception."""
   ExpectException(Vmodl.Fault.NotImplemented, callable, *args, **kwargs)


def ExpectNotFound(callable, *args, **kwargs):
   """Helper function that invokes the given callable and expects it
   to throw the standard not-found exception."""
   # XXX hbrsrv still seems to throw SystemError in these cases ..
   ExpectException(Vmodl.Fault.SystemError, callable, *args, **kwargs)


def ExpectManagedObjectNotFound(callable, *args, **kwargs):
   """Helper function that invokes the given callable and expects it
   to throw the standard managed-object-not-found exception."""
   ExpectException(Vmodl.Fault.ManagedObjectNotFound, callable, *args, **kwargs)


def RunCommand(cmdlist):
   rc = subprocess.call(cmdlist)
   if rc != 0:
      raise TestFailedExc("Error running " + cmdlist[0] + ": returned: " +
                          str(rc))

