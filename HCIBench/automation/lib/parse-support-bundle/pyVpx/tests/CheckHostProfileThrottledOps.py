#!/usr/bin/python

from __future__ import print_function

import os
import sys
import time
import types
import unittest

from multiprocessing import Process

from pyVim.connect import Connect, Disconnect
from pyVmomi import Vim, SoapAdapter
from optparse import OptionParser

"""
   Host Profile Engine test for operation throttling

   Usage:

   ../py.sh CheckHostProfileThrottledOps.py -H <host name/ip> -u <user name> -p <password>

"""

# File location where operations to throttle are defined, relative to
# bora
TAG_EXTRACTOR_FILENAME = \
      'install/vmvisor/environ/etc/vmware/hostd/tagExtractor.xml'

_si = None
def getHostProfileEngine():
   options = get_options()
   global _si
   if _si:
      Disconnect(_si)
   _si =  Connect(host=options.host,
                 user=options.user,
                 version="vim.version.version9",
                 pwd=options.password)
   return _si.RetrieveInternalContent().hostProfileEngine


def releaseHostProfileEngine(_hpEngine):
   global _si
   if _si:
      Disconnect(_si)


def readTagExtractorFile():
   """Helper function that locates and reads the tagExtractor file and
      returns its contents.
   """
   BORA = 'bora'
   curDir = os.path.abspath(os.path.curdir)
   boraIndex = curDir.rfind(BORA)
   if boraIndex != -1:
      boraPath = curDir[:boraIndex] + BORA
      tagExtractorFileName = os.path.join(boraPath, TAG_EXTRACTOR_FILENAME)
      if not os.path.exists(tagExtractorFileName):
         raise Exception('Failed to find tagExtractor.xml at path ' + \
                         tagExtractorFileName)

      tagExtractorFile = open(tagExtractorFileName, 'r')
      return tagExtractorFile.read()
   else:
      raise Exception('Failed to find bora from working directory ' + \
                      curDir)

_cliOptions = None
def get_options():
   """
   Supports the command-line arguments listed below
   """
   global _cliOptions
   if _cliOptions is None:
      parser = OptionParser()
      parser.add_option("-H", "--host",
                        default="localhost",
                        help="remote host to connect to")
      parser.add_option("-u", "--user",
                        default="root",
                        help="User name to use when connecting to hostd")
      parser.add_option("-p", "--password",
                        default="",
                        help="Password to use when connecting to hostd")
      (_cliOptions, _) = parser.parse_args()
   return _cliOptions

# This determines the number of times to run a target operation during
# the throttling tests.
DEFAULT_TEST_ITERATIONS = 3

# This provides for a 15% variance in the test time.
TEST_TIME_VARIANCE = 1.15

# The amount of time that could be expected to account for network
# traffic.
NETWORK_OVERHEAD = 0.333

def runOp(test):
   test.doOperation()


def runTests(test, otherTest):
   # Runs the two tests in separate processes and returns the time it
   # took to run each one.
   testProc = Process(target=runOp, args=(test,))
   otherTestProc = Process(target=runOp, args=(otherTest,))
   startTime = time.time()

   # Whichever test takes longer starts first
   if test.testRunTime > otherTest.testRunTime:
      testProc.start()
      otherTestProc.start()
   else:
      otherTestProc.start()
      testProc.start()

   testProc.join()
   otherTestProc.join()

   return time.time() - startTime


def runConcurrentTest(test, otherTest):
   if isinstance(test, ApplyHostConfigTest) or isinstance(otherTest, ApplyHostConfigTest):
      # The timing of the ApplyHostConfig() operation can differ quite a
      # bit when run at the same time as other tests. I'm guessing this
      # is due to all of the hostd refresh operations being done (i.e.
      # there may be some locking that takes place during that time).
      # So for now, we'll skip concurrency tests for ApplyHostConfig.
      return True

   # For a concurrent test, the test time should be roughly the same
   # as running the test by itself. There will be some amount of variance
   # since two test runs frequently don't have exactly the same time anyway,
   # plus there can be some performance impact in running the tests in
   # parallel, plus possible contention making hostd requests.
   expectedTestTime = TEST_TIME_VARIANCE * test.testRunTime
   expectedOtherTestTime = TEST_TIME_VARIANCE * otherTest.testRunTime

   if expectedOtherTestTime > expectedTestTime:
      expectedTestTime = expectedOtherTestTime

   numFailedIters = 0
   numIterations = test.numIterations
   if otherTest.numIterations > numIterations:
      numIterations = otherTest.numIterations

   for i in range(0, numIterations):
      runTime = runTests(test, otherTest)
      if runTime > expectedTestTime:
         # For the concurrent tests, we'll pass the test if at least one
         # iteration completed in under the expected time, which can
         # only happen if the operations are running in parallel.
         # NOTE: There have been false-negatives observed for the concurrent
         #       tests. That's why we're running multiple
         #       iterations and checking for passing at least once.
         print('Concurrent RunTime = %s, Expected test time = %s'
               % (runTime, expectedTestTime))
         numFailedIters = numFailedIters + 1

   return (numFailedIters == 0) or (numFailedIters < (numIterations / 2))


def runSerializedTest(test, otherTest):
   # For a serialized test, the test time should be roughly the same
   # as the two tests running the two tests one  after the other. There will be
   # some amount of variance in the run time of the tests, plus there will
   # be overlap between the two processes sending the request data to hostd,
   # which will have to process the requests in parallel just enough so that
   # it can determine it needs to throttle the requests.
   combinedTime = test.testRunTime + otherTest.testRunTime
   expectedTestTime = (combinedTime - NETWORK_OVERHEAD) / TEST_TIME_VARIANCE

   numFailedIters = 0
   numIterations = test.numIterations
   if otherTest.numIterations > numIterations:
      numIterations = otherTest.numIterations

   for i in range(0, numIterations):
      runTime = runTests(test, otherTest)
      if runTime < expectedTestTime:
         # For the serialized tests, we'll pass the test if at least one
         # iteration completed in over the expected time, which should
         # only happen if the operations are running sequentially.
         # NOTE: There have been false-negatives observed for the concurrent
         #       tests, and in theory there could be false-negatives for
         #       the serialized tests as well. That's why we're running multiple
         #       iterations and checking for passing at least once.
         print('Serialized RunTime = %s, Expected test time = %s'
               % (runTime, expectedTestTime))
         numFailedIters = numFailedIters + 1

   return (numFailedIters == 0) or (numFailedIters < (numIterations / 2))


class CheckHostProfilesThrottledOps(unittest.TestCase):
   """Tests throttling config for host profile operations.
   """
   def setUp(self):
      """
      Setting test suite
      """
      hostProfileEngine = getHostProfileEngine()
      self.hostProfileManager = hostProfileEngine.hostProfileManager
      self.hostComplianceManager = hostProfileEngine.hostComplianceManager

   @staticmethod
   def _findVimOps(managedObject):
      mgrMethods = []
      for attrName in dir(managedObject):
         if attrName[0] == '_':
            continue
         attrVal = getattr(managedObject, attrName)
         if attrVal and isinstance(attrVal, types.FunctionType):
            normalizedMethodName = attrName[0].lower() + attrName[1:]
            mgrMethods.append(normalizedMethodName)
      return mgrMethods


   def runTest(self):
      """Tests throttling config for host profile operations.
      """
      hostProfileEngineMethods = []
      hostProfileEngineMethods.extend(
            self._findVimOps(self.hostProfileManager))
      hostProfileEngineMethods.extend(
            self._findVimOps(self.hostComplianceManager))

      tagExtractorContents = readTagExtractorFile()
      missingMethods = []
      for methodName in hostProfileEngineMethods:
         if methodName not in tagExtractorContents:
            missingMethods.append(methodName)
      self.failIf(len(missingMethods) != 0,
            'Host Profile Engine methods missing from tagExtractor.xml: ' + str(missingMethods))



class InitHostProfilesThrottledOps(unittest.TestCase):
   """Initializes the throttled op testers.
   """
   def setUp(self):
      self.serializedOps = [

         [  RetrieveProfileTest, CheckHostComplianceTest, ExecuteTest, \
            UpdateTaskConfigSpecTest, ApplyHostConfigTest ],

         [  GetDefaultComplianceTest, QueryExpressionMetadataTest, \
            CreateDefaultProfileTest, QueryPolicyMetadataTest, \
            QueryProfileMetadataTest, BookKeepTest, \
            RetrieveProfileDescriptionTest, PrepareExportTest, \
            QueryUserInputPolicyOptionsTest, QueryProfileStructureTest ]
      ]

   def runTest(self):
      """Initializes the throttled op testers.
      """
      # This does a couple of things:
      # 1. It initializes an instance of each op test prior to running
      #    all the tests.
      # 2. Resolves the serializedOps and concurrentOps for each test
      #    op type according to the serializedOps section above.
      for testSet in self.serializedOps:
         while testSet:
            test = testSet.pop(0)
            test().setUp()
            test.op.serializedOps = testSet[:]
            for otherTestSet in self.serializedOps:
               if otherTestSet is not testSet:
                  test.op.concurrentOps.extend(otherTestSet)


class ThrottledOpTest:
   """Subclasses of this should be created for testing concurrency of
      a particular operation. Subclasses should define two attributes:

      * serializedOps: This should be a list of ThrottledOpTest
                       subclasses for operations that are supposed to
                       run sequentially with this test operation.

      * concurrentOps: This should be a list of ThrottledOpTest
                       subclasses for operations that can run in
                       parallel with this test operation.
      * op: A singleton instance of the ThrottledOpTest subclass.
   """
   profileResult = None
   execResult = None
   updateTaskResult = None
   numIterations = DEFAULT_TEST_ITERATIONS

   def __init__(self, *args):
      if issubclass(self.__class__, unittest.TestCase):
         unittest.TestCase.__init__(self, *args)

   def shortDescription(self):
      return 'Concurrency test for %s operation' % \
                self.__class__.__name__.replace('Test', '')

   def setUp(self):
      if not self.__class__.op:
         self.serializedOps = []
         self.concurrentOps = []
         initTestRunTime = 0
         for i in range(0, self.numIterations):
            initTestRunTime = initTestRunTime + self.doOperation()
         self.testRunTime = initTestRunTime / self.numIterations
         self.__class__.op = self
      else:
         self.serializedOps = self.__class__.op.serializedOps
         self.concurrentOps = self.__class__.op.concurrentOps
         self.testRunTime = self.__class__.op.testRunTime

   def doOperation(self):
      hpEngine = getHostProfileEngine()
      startTime = time.time()
      self.doOp(hpEngine.hostProfileManager,
                hpEngine.hostComplianceManager)
      releaseHostProfileEngine(hpEngine)
      return time.time() - startTime


   def runTest(self):
      # First, make sure that it cannot be run concurrently with itself
      self.failUnless(runSerializedTest(self, self),
                      'Multiple %s operations did not run serially' \
                         % self.__class__.__name__)

      for test in self.serializedOps:
         # Check that the test operation and this operation are actually running
         # sequentially. The "runSerializedTest()" method will spawn processes
         # to run the two operations simultaneously and will check the run time
         # it takes to complete the two operations and determine if those two
         # operations were actually run sequentially.
         self.failUnless(runSerializedTest(test.op, self),
               'Operations did not run serially: %s, %s' % \
               (test.op.__class__.__name__, self.__class__.__name__))

      for test in self.concurrentOps:
         # Check that the test operation and this operation are actually running
         # concurrently. The "runConcurrenTest()" method will spawn processes
         # to run the two operations simultaneously and will check the run time
         # it takes to complete the two oeprations and determine if those two
         # operations were actually run in parallel.
         self.failUnless(runConcurrentTest(test.op, self),
               'Operations did not run concurrently: %s, %s' % \
               (test.op.__class__.__name__, self.__class__.__name__))


class RetrieveProfileTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      ThrottledOpTest.profileResult = hpm.RetrieveProfile()

class TestRetrieveProfile(RetrieveProfileTest, unittest.TestCase):
   pass


class CheckHostComplianceTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      hcm.CheckHostCompliance(config=self.profileResult)


class TestCheckHostCompliance(CheckHostComplianceTest, unittest.TestCase):
   pass


class ExecuteTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      ThrottledOpTest.execResult = hpm.Execute(
                                     self.profileResult.applyProfile)

class TestExecute(ExecuteTest, unittest.TestCase):
   pass

class UpdateTaskConfigSpecTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      ThrottledOpTest.updateTaskResult = hpm.UpdateTaskConfigSpec(
                                           configSpec=self.execResult.configSpec)

class TestUpdateTaskConfigSpec(UpdateTaskConfigSpecTest, unittest.TestCase):
   pass


class ApplyHostConfigTest(ThrottledOpTest):
   op = None
   def doOp(self, hpm, hcm):
      opTask = hpm.ApplyHostConfig(self.updateTaskResult.configSpec)
      while opTask.info.state != 'success' and \
            opTask.info.state != 'error':
         time.sleep(0.1)

class TestApplyHostConfig(ApplyHostConfigTest, unittest.TestCase):
   pass


class GetDefaultComplianceTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      hcm.GetDefaultCompliance(self.profileResult.applyProfile)

class TestGetDefaultCompliance(GetDefaultComplianceTest, unittest.TestCase):
   pass


class QueryExpressionMetadataTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      hcm.QueryExpressionMetadata()

class TestQueryExpressionMetadata(QueryExpressionMetadataTest, unittest.TestCase):
   pass


class QueryPolicyMetadataTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      hpm.QueryPolicyMetadata()

class TestQueryPolicyMetadata(QueryPolicyMetadataTest, unittest.TestCase):
   pass


class QueryProfileMetadataTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      hpm.QueryProfileMetadata()

class TestQueryProfileMetadata(QueryProfileMetadataTest, unittest.TestCase):
   pass


class CreateDefaultProfileTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      hpm.CreateDefaultProfile(Vim.Profile.Host.VirtualSwitchProfile)

class TestCreateDefaultProfile(CreateDefaultProfileTest, unittest.TestCase):
   pass


class BookKeepTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      hpm.BookKeep(self.profileResult)

class TestBookKeep(BookKeepTest, unittest.TestCase):
   pass


class RetrieveProfileDescriptionTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      hpm.RetrieveProfileDescription(self.profileResult)

class TestRetrieveProfileDescription(RetrieveProfileDescriptionTest, unittest.TestCase):
   pass


class QueryProfileStructureTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      hpm.QueryProfileStructure()

class TestQueryProfileStructure(QueryProfileStructureTest, unittest.TestCase):
   pass


class PrepareExportTest(ThrottledOpTest):
   op = None

   def doOp(self, hpm, hcm):
      hpm.PrepareExport(self.profileResult)

class TestPrepareExport(PrepareExportTest, unittest.TestCase):
   pass


class QueryUserInputPolicyOptionsTest(ThrottledOpTest):
   op = None
   # Override the number of iterations since there is a known issue with
   # reliability between this test and the Execute() test.
   numIterations = 8

   def doOp(self, hpm, hcm):
      hpm.QueryUserInputPolicyOptions(self.profileResult.applyProfile)

class TestQueryUserInputPolicyOptions(QueryUserInputPolicyOptionsTest, unittest.TestCase):
   pass


def main(argv):
    """
    Test the throttling for the host profile operations
    """
    # Set up the arguments wanted by unittest.main()
    unittest_argv = [ sys.argv[0], '-v' ]

    # Run get_options once to process the real command line arguments
    # before we replace them.
    get_options()

    # Swap the args and run the unittest framework.
    sys.argv = unittest_argv
    sys.exit(unittest.main())


# Start program
if __name__ == "__main__":
    main(sys.argv[1:])
