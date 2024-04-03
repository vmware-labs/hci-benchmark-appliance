#!/usr/bin/python

#
# Basic tests for Vim::Vm::Guest::ProcessManager
#
# These require the latest tools on a VM with a supported guest
#

from pyVmomi import Vim, Vmodl
from pyVim.connect import SmartConnect
from pyVim.helpers import Log
from guestOpsUtils import *

def testFullEnvVars():
   # positive test that queries all env vars
   Log("Testing ReadEnvVariables all()")
   result  = procMgr.ReadEnvironmentVariable(virtualMachine, guestAuth, None)
   Log('Full env vars: {0}'.format(result))

def testSingleEnvVars():
   # single var test
   Log("Testing ReadEnvVariables $PATH")
   result  = procMgr.ReadEnvironmentVariable(virtualMachine, guestAuth, "PATH")
   Log("$PATH: %s" % result)
   result  = procMgr.ReadEnvironmentVariable(virtualMachine, guestAuth, "TMP")
   Log("$TMP: %s" % result)

def testFullListProc():
   # should return all processes
   Log("Testing ListProcesses all")
   result  = procMgr.ListProcesses(virtualMachine, guestAuth, None)
   Log("All processes: %s" % result)

def testExplicitListProc():
   # explicit pid test -- try some system processes that should be there
   pids = [0, 1, 2]
   Log("Testing explicit ListProcesses pid %s" % pids)
   result  = procMgr.ListProcesses(virtualMachine, guestAuth, pids)
   Log("Note that this may have 0 results on Windows")
   numResults = len(result)
   Log("Found %s results" % numResults)
   if numResults > 0:
      Log("Explicit processes: %s" % result)
      for process in result:
         found = False
         for pid in pids:
            if process.pid == pid:
               Log("Found pid %s" % pid)
               found = True
               break
         if not found:
            Log("Unwanted pid %s" % process.pid)
            raise AssertionError("Received unwanted pid %s" % process.pid)

def testBasicStartProg():
   Log("Testing StartProgram")
   spec = procDef.ProgramSpec(programPath="/bin/ls", workingDirectory="/dev", arguments="> /tmp/ls.out")
   result  = procMgr.StartProgram(virtualMachine, guestAuth, spec)
   Log("Pid %s" % result)
   Log("Testing StartProgram2")
   spec = procDef.ProgramSpec(programPath="/usr/bin/env", workingDirectory="/dev", arguments="> /tmp/env.out")
   result  = procMgr.StartProgram(virtualMachine, guestAuth, spec)
   Log("Pid %s" % result)

def testDeadProc():
   Log("Testing StartProgram")
   spec = procDef.ProgramSpec(programPath="/bin/ls", arguments="/tmp")
   pid  = procMgr.StartProgram(virtualMachine, guestAuth, spec)
   Log("Pid %s" % pid)
   pids = [ pid ]
   result  = procMgr.ListProcesses(virtualMachine, guestAuth, pids)
   Log("Expected process not to show completion (no endTime or exitCode) yet")
   Log("Process info %s" % result)
   Log("Sleeping 3 seconds")
   time.sleep(3)
   result  = procMgr.ListProcesses(virtualMachine, guestAuth, pids)
   Log("Expected process to show full results now")
   Log("Process info %s" % result)

def testBasicTerminateProg():
   Log("Starting Program")
   spec = procDef.ProgramSpec(programPath="/bin/sleep", arguments="3600")
   pid  = procMgr.StartProgram(virtualMachine, guestAuth, spec)
   Log("Pid %s" % pid)
   pids = [ pid ]
   result  = procMgr.ListProcesses(virtualMachine, guestAuth, pids)
   Log("Expected process not to show completion (no endTime or exitCode) yet")
   Log("Process info %s" % result)
   Log("Sleeping 3 seconds")
   time.sleep(3)
   Log("Terminating Program")
   result  = procMgr.TerminateProcess(virtualMachine, guestAuth, pid)
   Log("Sleeping 3 seconds")
   time.sleep(3)
   result  = procMgr.ListProcesses(virtualMachine, guestAuth, pids)
   Log("Expected process to show full results now")
   Log("Process info %s" % result)

def main():

   # Process command line
   options = get_options()

   global svcInst
   global virtualMachine
   global guestAdminAuth
   global guestAuth
   global guestAuthBad
   [svcInst, virtualMachine, guestAdminAuth,
    guestAuth, guestAuthBad] = init(options.host, options.user, options.password,
                                    options.vmname, options.vmxpath, options.guestuser,
                                    options.guestpassword, options.guestrootuser,
                                    options.guestrootpassword)

   # get the processManager object
   global procMgr
   procMgr = svcInst.content.guestOperationsManager.processManager
   global procDef
   procDef = Vim.Vm.Guest.ProcessManager

   testNotReady(procMgr, virtualMachine, guestAuth)
   waitForTools(virtualMachine)

   testFullEnvVars()
   testSingleEnvVars()
   testFullListProc()
   testExplicitListProc()
   testBasicStartProg()
   testDeadProc()
   testBasicTerminateProg()

# Start program
if __name__ == "__main__":
   main()
   Log("processManager tests completed")
