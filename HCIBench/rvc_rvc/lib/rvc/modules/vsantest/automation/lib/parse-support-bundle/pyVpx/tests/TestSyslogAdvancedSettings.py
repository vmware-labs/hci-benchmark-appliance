#!/usr/bin/python

from __future__ import print_function

import sys, time
import os
import unittest

from pyVmomi import vim, vmodl
from pyVim.connect import Connect, Disconnect
from optparse import OptionParser
from pyVim import folder
from pyVim import host

"""
   Test Advanced Options for Syslog configuration.

   Test deprecated options:
      Syslog.Local.DatastorePath
      Syslog.Remote.Hostname
      Syslog.Remote.Port
   Test new options (global):
      Syslog.global.defaultRotate
      Syslog.global.defaultSize
      Syslog.global.logDir
      Syslog.global.logDirUnique
      Syslog.global.logHost
   Test new options (logger specific):
      Syslog.loggers.hostd.rotate
      Syslog.loggers.hostd.size

   Usage:
   ../py.sh TestSyslogAdvancedSettings.py -H <host name/ip> -u <user name> -p <password>

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
    (options, _) = parser.parse_args()
    return options


class TestSyslogAdvancedSettings(unittest.TestCase):

   def setUp(self):
      """
      Setting test suite
      """
      self.options = get_options()

      self.si = Connect(host=self.options.host,
                        user=self.options.user,
                        version="vim.version.version9",
                        pwd=self.options.password)
      content = self.si.RetrieveContent()
      rootFolder = content.rootFolder
      dataCenter = rootFolder.childEntity[0]
      hostFolder = dataCenter.hostFolder
      host = hostFolder.childEntity[0]
      self.hostSystem = host.host[0]
      self.assertTrue(self.hostSystem != None,
                      "hostSystem should not be None.")
      self.advancedOption = self.hostSystem.configManager.advancedOption
      self.assertTrue(self.advancedOption != None,
                      "advancedOption should not be None.")

   def tearDown(self):
      """
      Reset test suite
      """
      Disconnect(self.si)

   def runTest(self):
      # self.TestDeprecatedOptions()
      self.TestGlobalOptions()
      self.TestLogDirChange()


   def TestDeprecatedOptions(self):
      """
      Test the behaviour of deprecated options.
      """

      print("\nTest deprecated options")

      # save original logHost
      ov = self.advancedOption.QueryView("Syslog.global.logHost")
      savedLogHost = ov[0].value

      # change logHost
      ov[0].value = "127.0.0.1:333, localhost"
      if len(savedLogHost) > 0:
         ov[0].value = ov[0].value + ", " + savedLogHost
      self.advancedOption.UpdateValues(ov)

      try:
         # verify Hostname and Port
         ov = self.advancedOption.QueryView("Syslog.Remote.Hostname")
         self.assertTrue(ov[0].value == "127.0.0.1",
                         "Hostname must be '127.0.0.1'.")
         ov = self.advancedOption.QueryView("Syslog.Remote.Port")
         self.assertTrue(ov[0].value == 333,
                         "Port must be 333.")
      finally:
         # restore logHost
         ov[0].key = "Syslog.global.logHost"
         ov[0].value = savedLogHost
         self.advancedOption.UpdateValues(ov)


   def TestGlobalOptions(self):
      """
      Test new global options
      """

      print("\nTest global options")

      # save original defaultRotate
      ov = self.advancedOption.QueryView("Syslog.global.defaultRotate")
      savedDefRotate = ov[0].value

      # change defaultRotate
      ov[0].value = 33
      self.advancedOption.UpdateValues(ov)

      try:
         # verify vmkernel.rotate = new value
         ov = self.advancedOption.QueryView("Syslog.loggers.vmkernel.rotate")
         self.assertTrue(ov[0].value == 33,
                         "vmkernel.rotate must be 33.")
      finally:
         # restore defaultRotate
         ov[0].key = "Syslog.global.defaultRotate"
         ov[0].value = savedDefRotate
         self.advancedOption.UpdateValues(ov)


   def TestLogDirChange(self):
      """
      Test changing the location of log output.
      """

      print("\nTest logdir option")

      # save original logDir
      ov = self.advancedOption.QueryView("Syslog.global.logDir")
      savedLogDir = ov[0].value

      # change logDir
      ov[0].key = "Syslog.global.logDir"
      testLogDir = "/tmp/log_test_%d" % time.time()
      ov[0].value = "[] " + testLogDir
      self.advancedOption.UpdateValues(ov)

      try:
         # Write a message to Vpxa log
         message = "TEST_LOG_MESSAGE_%d" % time.time()
         retval = os.system("logger -t Vpxa %s" % message)
         self.assertTrue(retval == 0, "retval = %d, must be 0." % retval)

         # Find the above message in vpxa.log file
         vpxaLogFile = testLogDir + "/vpxa.log"
         for i in range(3):
            time.sleep(1)
            retval = os.system("grep -q '%s' %s" % (message, vpxaLogFile))
            if retval == 0:
               break
         self.assertTrue(retval == 0,
            "Message '%s' not found in file '%s'." % (message, vpxaLogFile))
      finally:
         # restore logDir
         ov[0].key = "Syslog.global.logDir"
         ov[0].value = savedLogDir
         self.advancedOption.UpdateValues(ov)


# Start program
if __name__ == "__main__":
   sys.exit(unittest.main())
