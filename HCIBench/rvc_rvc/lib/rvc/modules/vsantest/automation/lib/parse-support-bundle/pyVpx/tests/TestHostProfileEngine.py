#!/usr/bin/python
import sys, time
import unittest
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import Vim, SoapAdapter
from pyVmomi.VmomiSupport import newestVersions
from optparse import OptionParser

"""
   Host Profile Engine API Test

   Usage:

   ../py.sh TestHostProfileEngine.py -H <host name/ip> -u <user name> -p <password>

"""
def get_options():
    """
    Supports the command-line arguments listed below
    """

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
    parser.add_option("-v", "--vimversion",
                      default=None,
                      help="VIM version to use when connecting to hostd, " + \
                           "e.g. vim.version.version9 " + \
                           "(default is to use latest available version)")
    (options, _) = parser.parse_args()
    return options


TEST_DATASTORE_NAME = 'hpTestNfsDatastore'


class TestHostProfileEngine(unittest.TestCase):
   """Tests most of the interesting commands for the host profile
      engine.
   """
   def setOptions(self, options):
      """
      Command line options
      """
      self.options = options


   def cleanupTestDatastore(self):
      hostView = self.si.content.viewManager.CreateContainerView(
                       self.si.content.rootFolder, [Vim.HostSystem], True)
      if len(hostView.view) != 1:
         raise Exception('Unable to find host to clean up NAS datastores')

      datastoreSystem = hostView.view[0].configManager.datastoreSystem
      for ds in datastoreSystem.datastore:
         if ds.summary.name == TEST_DATASTORE_NAME:
            datastoreSystem.RemoveDatastore(ds)
            break


   def setUp(self):
      """
      Setting test suite
      """
      options = get_options()

      self.si = SmartConnect(host=self.options.host,
                             user=self.options.user,
                             preferredApiVersions=self.options.vimversion,
                             pwd=self.options.password)

      # Make sure that the test datastore is not on the system in case a
      # previous test run had failed and left the test datastore on the system
      self.cleanupTestDatastore()

      internalContent = self.si.RetrieveInternalContent()
      hostProfileEngine = internalContent.hostProfileEngine
      self.hostProfileManager = hostProfileEngine.hostProfileManager
      self.hostComplianceManager = hostProfileEngine.hostComplianceManager
      self.answerFileData = None

      # Make sure that hostd's cache is valid. This is needed in cases where
      # a user has made changes using localcli, esxcfg, or DCUI that have not
      # propagated to hostd.
      self.refreshHostdCache()


   def tearDown(self):
      """
      Reset test suite
      """
      # The test datastore may not have been deleted if there was an error in
      # the middle of the test. Make sure it gets cleaned up.
      self.cleanupTestDatastore()

      Disconnect(self.si)


   def refreshHostdCache(self):
      """Refresh hostd's cache by doing a no-op Apply operation.
      """
      # Build an empty config spec and apply
      configSpec = Vim.Host.ConfigSpec()
      applyTask = self.hostProfileManager.ApplyHostConfig(configSpec)

      taskTimeout = 2.5 * 60 # 2.5 mins
      waitPeriod = 1

      # Check the task completed or if we hit the timeout
      while applyTask.info.progress != 100 and taskTimeout != 0:
         time.sleep(waitPeriod)
         taskTimeout -= waitPeriod


   def runTest(self):
      """Tests most of the interesting commands for the host profile
         engine.
      """
      self.test_extractProfile()
      self.test_createDefaultProfile()
      self.test_bookKeep()
      self.test_generateAnswerFile()
      self.test_checkCompliance()
      self.test_generateConfigTasks()
      self.test_applyConfigTasks()
      self.restoreOriginalConfig()


   def _copyHostProfile(self, hostProfile):
      """Helper function that makes a copy of the host profile document.
      """
      # TBD: Is there a better way than serializing/deserializing?
      serializedProf = SoapAdapter.Serialize(hostProfile,
                                             version=newestVersions.GetName('vim'))
      deserializedProf = SoapAdapter.Deserialize(serializedProf)
      return deserializedProf


   def test_extractProfile(self):
      """Performs a RetrieveProfile() operation and saves the results.
      """
      # Let's do it twice: once to capture the original configuration and once
      # to create a new profile that can be modified and applied.
      self.origConfigProfile = self.hostProfileManager.RetrieveProfile()
      self.testProfile = self._copyHostProfile(self.origConfigProfile)

      # Make sure that the basic components are there
      self.failIf(self.testProfile is None or \
                  not hasattr(self.testProfile, 'applyProfile') or \
                  self.testProfile.applyProfile is None or \
                  not hasattr(self.testProfile, 'defaultComplyProfile') or \
                  self.testProfile.defaultComplyProfile is None,
                  'Invalid host profile extracted from host')

      applyProfile = self.testProfile.applyProfile

      # Now make sure that at least the Storage and NAS profiles are there.
      self.failIf(not hasattr(applyProfile, 'storage') or \
                  applyProfile.storage is None,
                  'Extracted host profile missing Storage profile')
      storageProfile = applyProfile.storage

      self.failIf(not hasattr(storageProfile, 'nasStorage') or \
                  storageProfile.nasStorage is None,
                  'Extracted host profile missing NAS Storage profile')


   def test_createDefaultProfile(self):
      """Performs a CreateDefaultProfile() operation to create a NFS datastore
         in the test profile.
      """
      newNasDatastore = self.hostProfileManager.CreateDefaultProfile(
                              profileType=Vim.Profile.Host.NasStorageProfile,
                              profileTypeName=None)

      self.failIf(newNasDatastore is None,
                  'Failed to create new NAS datastore profile instance')

      # Set the parameters for the Nas datastore. Pick a NFS host that
      # everyone should have access to, but a remotePath that probably
      # no one has mounted.
      for param in newNasDatastore.policy[0].policyOption.parameter:
         if param.key == 'localPath':
            param.value = TEST_DATASTORE_NAME
         elif param.key == 'remoteHost':
            param.value = 'build-toolchain.eng.vmware.com'
         elif param.key == 'remotePath':
            param.value = '/toolchain/lin32/python-2.5/man'

      # Save it in the testProfile
      self.testProfile.applyProfile.storage.nasStorage.append(newNasDatastore)


   def test_bookKeep(self):
      """Performs a BookKeep() operation on the test profile.
      """
      verifiedProfile = self.hostProfileManager.BookKeep(self.testProfile)
      defComplyProf = self.hostComplianceManager.GetDefaultCompliance(
                           verifiedProfile.applyProfile)
      defComplyProf.applyProfile = verifiedProfile.applyProfile
      self.testProfile = defComplyProf


   def test_checkCompliance(self, expectedNonCompliant=True):
      """Checks compliance with the test profile.
      """
      complyResult = self.hostComplianceManager.CheckHostCompliance(
                           self.testProfile, deferredParam=self.answerFileData)
      if expectedNonCompliant:
         self.failUnless(complyResult.complianceStatus == 'nonCompliant',
            'Unexpected compliance result: ' + str(complyResult))
      else:
         self.failUnless(complyResult.complianceStatus == 'compliant',
            'Unexpected compliance result: ' + str(complyResult))


   def test_generateAnswerFile(self):
      """Generates a default answer file to be used with the checkCompliance
         and generateConfigTasks tests.
      """
      execRes = self.hostProfileManager.Execute(self.testProfile.applyProfile)
      if execRes.status == 'needInput':
         self.answerFileData = execRes.requireInput
      else:
         self.failIf(execRes.status != 'success',
            'Unexpected Execute result in generateAnswerFile: ' + str(execRes))


   def test_generateConfigTasks(self):
      """Generates the config spec for applying the test profile.
      """
      execRes = self.hostProfileManager.Execute(self.testProfile.applyProfile,
                                                deferredParam=self.answerFileData)
      self.failIf(execRes.status != 'success',
            'Unexpected Execute result in generateConfigTasks: ' + str(execRes))

      updatedConfigSpec = self.hostProfileManager.UpdateTaskConfigSpec(
                                configSpec=execRes.configSpec)

      foundNfsTask = False
      for task in updatedConfigSpec.taskDescription:
         if 'hpTestNfsDatastore' in task.message:
            foundNfsTask = True
            break

      self.failIf(foundNfsTask == False,
                  'Failed to find task data and message for new NAS datastore')
      # Save the part needed for ApplyConfigTasks
      self.configSpec = updatedConfigSpec.configSpec


   def _waitForTask(self, task):
      """Helper method that waits for a task to complete.
      """
      while task.info.state == 'running':
         time.sleep(1)

   def test_applyConfigTasks(self):
      """Applies the config spec created for the test profile.
      """
      task = self.hostProfileManager.ApplyHostConfig(
                   configSpec=self.configSpec)
      while task.info.state == 'running':
         time.sleep(1)

      self.failIf(task.info.state != 'success', 'Apply task failed:\n' + str(task.info))

      # Check compliance again. Should be compliant this time.
      self.test_checkCompliance(expectedNonCompliant=False)

   def restoreOriginalConfig(self):
      """Restores the original configuration according to the host profile
         document collected at the beginning of the test.
      """
      # The simplest way to implement this is to replace the testProfile with
      # the original profile and then re-run the test_generateConfigTasks()
      # and test_applyConfigTasks.

      self.testProfile = self.origConfigProfile
      self.test_generateConfigTasks()
      self.test_applyConfigTasks()


def main(argv):
    """
    Test Host Profile Engine VModl API
    """
    options = get_options()
    test = TestHostProfileEngine()
    test.setOptions(options)
    suite = unittest.TestSuite()
    suite.addTest(test)
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    if res.errors or res.failures:
       sys.exit(1)


# Start program
if __name__ == "__main__":
    main(sys.argv[1:])
