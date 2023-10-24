#!/usr/bin/python
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential

## @file integDriver.py --
# @brief Purpose: to invoke HOSTD Integration Tests
# Reads an xml config file then executes testoob module, results stored
# in an xml file for later comparison
# - Compatibility: Python 2.2 and up
#

__author__ = "VMware, Inc."

import os
import sys
from xml.sax import handler, make_parser
import re
import unittest
import testoob
import logging

## Main program subroutine
# @param argv [in] contains the filename of the xml file
# @post subcommand invoked based on xml file
def _Main():
   logging.basicConfig(level=logging.DEBUG,
                       format='%(asctime)s [%(levelname)s] %(message)s',
                       datefmt='%Y-%m-%d %H:%M:%S')

   optArgs = ParseOptions()
   if optArgs.debug:
      import pdb
      pdb.set_trace()

   LoadHostdDependencies()

   # Register with testoob's Asserter for verbose asserts
   from pyVim.integtest import RegisterAsserters
   RegisterAsserters()

   LoadAndRunTests(optArgs)
   logging.info("Done.")


## Setup sys.path for vmacore/vmomi based tests
# @todo: XXX move these to config.xml
# @post sys.path updated, import pyVmomi works
def LoadHostdDependencies():
   sys.path.append(os.path.abspath("."))
   SetVmodlPath()

## Run vmrepo to setup test data files (VMs)
# @param useDefault [in] controls which vmInventory.xml to use
# @pre scripts vmrepo.py and mgmt-hostd exist
# @post hostd in a known, reproducible state to start testing on.
#       On error throw exception
def SyncUpTestData(useDefault=False):
   logging.info("Resetting VMs, vmInventory, and backing up hostd state")
   cmd = "python vmrepo.py --sync"
   if useDefault is True:
      cmd += " -b"
   rc = os.system(cmd)
   if (rc >> 8) != 0:
      raise Exception("ERROR: %s failed %d" % (cmd, rc))
   logging.info("VMs, vmInventory state reset.")

## Update python interpreter PYTHONPATH to include pyVmomi module
# @post sys.path contains path to vmodl/pyVmomi python module
def SetVmodlPath():
   vmp = None
   # @todo: Fix this stuff properly!
   if os.environ.has_key('BUILDROOT'):
      vmp = os.path.join(os.environ['BUILDROOT'], "vmodl")
   else:
      vmp = "../../../../../devel/linux32/obj/esx/rpm/hostd/stage/usr/lib/python2.4/site-packages"
      logging.info("Using pyVmomi from: %s" % vmp)
   # localize path to OS filesystem
   vmp = os.path.abspath(vmp)
   if not os.path.exists(vmp):
      raise Exception("Can't find location of vmodl/pyVmomi, set BUILDROOT or VMTREE")
   if not os.path.exists(os.path.join(vmp, "pyVmomi")):
      raise Exception("python module pyVmomi not found, check value or set BUILDROOT or VMTREE")
   sys.path.append(vmp)

def _exc_info():
   """Return a version of sys.exc_info() with the traceback frame
      minimised; usually the top level of the traceback frame is not
      needed.
   """
   exctype, excvalue, tb = sys.exc_info()
   if sys.platform[:4] == 'java': ## XXX: tracebacks look different in Jython
       return (exctype, excvalue, tb)
   return (exctype, excvalue, tb)

## Setup and run test cases
# @param options [in] contains cmd ine settings
# @pre file integTests.xml exists, is readable
# @post tests run, output xml file: results exists
def LoadAndRunTests(options=None):
   if options is None or len(options.params) == 0:
      name = 'integTests.xml'
      options.params.append(name)
   else:
      name = options.params[0]
   if options.no_sync is None:
      useDefault = False
      if options.use_default is not None:
         useDefault = True
      if options.dry_run is None:
         SyncUpTestData(useDefault)
   else:
      logging.info("VM and hostd data not sync'd by operator command")
   if os.path.exists(name):
      prc = TestOptionParser(name)
      prc.Parse()
      if options.creds is not None:
         prc.UpdateCreds(options.creds)
      prc.SetConnectionInfo(options.type)
      optArgs = prc.GetOpts()
      testDir = './integtests.d'
      if not os.path.exists(testDir):
         raise IOError("Missing directory contianing tests: " + testDir)
      logging.info("Loading Tests...")
      mods = prc.GetModuleList(testDir)
      if len(mods) == 0:
         raise IOError("No test modules were found(or enabled)")
      try:
         skippedMods = []
         for ix in mods:
            try:
               __import__(ix)
            except ImportError, msg:
               skippedMods.append((ix, sys.exc_info()))
               mods.remove(ix)

         suite = unittest.TestLoader().loadTestsFromNames(mods)
         if options.filter:
            ftr = FilterSuite(suite, options.filter)
            suite = ftr.GetSuite()
         if options.dry_run:
            if suite.countTestCases() == 0:
               logging.info("No TestCases found in TestSuite")
               return
            print "Tests selected to run are:"
            tests = {} # key is name of TestCase class, data is list of test_*()
            CollectTests(suite, tests)
            objs = 0
            funcs = 0
            for item in tests.keys():
               print " ", item
               objs += 1
               for test in tests[item]:
                  print "    ", test
                  funcs += 1
            logging.info("Totals: TestCases: %d Functions: %d " % (objs, funcs))
            return
         ##try:
         logging.info("Starting Tests")
         testoob.main(suite, None, **optArgs)
         ##except SystemExit, arg:
         if len(skippedMods) > 0:
            logging.error("%s test(s) failed to load." % (len(skippedMods),))
            import traceback
            for testName, err in skippedMods:
               print ">>> %s\n%s" % (
                  testName, ''.join(traceback.format_exception(*err)))
            ##raise
      except ImportError:
         raise IOError("Loading test module failed, see prior error.")
   else:
      raise IOError('file not found')

## Extract options from command line
# @return an object containing parsed cmd line arguments
def ParseOptions():
   try:
      import optparse
   except ImportError:
      from testoob.compatibility import optparse

   usage = "usage: %prog [options] integTests.xml"
   formatter = optparse.TitledHelpFormatter(max_help_position=30)
   popt = optparse.OptionParser(usage=usage, formatter=formatter)
   popt.add_option("-n", "--dry-run", action="store_true",
                   help="Display what tests would be run")
   popt.add_option("-c", "--creds", action="store", type="string", dest="creds",
                   help="Specify Login info, format=host:port:user:passwd")
   popt.add_option("-t", "--type", action="store", type="string", dest="type",
                   help="Specify protocol type, values: vmdb|soap, defaults vmdb")
   popt.add_option("-f", "--filter", action="append", type="string", dest="filter",
           help="Specify regex filter to apply to tests loaded from config file")
   popt.add_option("-d", "--debug", action="store_true",
                   help="Step trace integDriver")
   popt.add_option("-r", "--no-sync", dest="no_sync", action="store_true", default=False,
                   help="Do not run vmrepo.py to reset hostd state before starting tests")
   popt.add_option("-s", "--sync", dest="no_sync", action="store_false",
                   help="Run vmrepo.py to reset hostd state before starting tests")
   popt.add_option("-b", "--use-default", action="store_true",
                   help="Use /etc/vmware/hostd/vmInventory.xml and /etc/init.d/mgmt-vmware script")
   options, parameters = popt.parse_args()
   options.params = parameters  # hackish, modify object to return parameters
   # remove sys.argv everything but first and last arg, testoob won't ignore
   sys.argv = [sys.argv[0]]
   return options

## Filter out tests specified in suite
# @param suite [in] is a class unittest.TestSuite
# @param: tests [in] is a dictionary of class UnitTests, with list of member functions
# @post contents of suite dumped to stdout
# @todo: make an iterator object, see _visitAll
def CollectTests(suite,
                 tests):
   if suite is None:
      logging.warning("No suite given to display.")
      return

   if isinstance(suite, unittest.TestSuite):
      for item in suite._tests:
         try:
            getattr(item, 'addTests') # is this a TestSuite?
            CollectTests(item, tests)
         except AttributeError:
            tests[str(item.__class__)] = []
            for elem in dir(item):
               if elem.startswith('test'):
                  tests[str(item.__class__)].append(elem)
      else:
         return


## Handle all options  for running tests here
class TestOptionParser(handler.ContentHandler):
   _parser = None
   _re = re.compile(r'([_\w][\w_-]+)')   # xml element name
   _count = 0                   # number of elements started
   _file = None                 # source xml file name
   _name = None                 # current xml element
   _data = ""                   # data associated with _name
   _avp = {}                    # xml element/data map
   _testModules = []            # test modules to run
   _inModules = False           # section of xml defining test modules
   _parseState = []             # track which xml elements we've seen

   ## @pre file specifies path to xml config file
   ## @post sax parser initialized, file saved in object
   def __init__(self,
                file):
      handler.ContentHandler.__init__(self)
      self._file = file

   ## @return redundant whitespace from a string removed
   def _fixWhitespace(self,
                      text):
      return ''.join(text.split())

   def startElement(self,
                    name,
                    attrs):
      self._parseState.append(name)
      self._name = self._fixWhitespace(name)
      self._count += 1;
      self._data = ""
      # read names of test modules to run
      if self._name == "TestDriver":
         self._inModules = True

   def endElement(self,
                  name):
      name = self._fixWhitespace(name)
      if name == "TestDriver":
         self._inModules = False
         return
      # direct children of TestDriver are modules
      if self._inModules:
         if self._parseState[-2] == "TestDriver":
            if self._getBoolValue('enabled'):
               self._testModules.append(name)
      if len(name) > 0:
         try:
            item = self._re.search(self._name)
            self._name = item.groups()[0]
            self._avp[self._name] = self._fixWhitespace(self._data)
         except TypeError:
            pass
      self._name = None
      self._data = ""
      self._parseState.pop()

   def characters(self,
                  info):
      self._data += info

   ## Return boolean of config options
   # @pre elemName exists
   # @post return true if elemName exists and has the word 'true'
   #       (case-insensitive) else return false
   def _getBoolValue(self,
                     elemName):
      if not self._optionExists(elemName):
         return False
      if re.search(r'\s*true\s*', self._avp[elemName],
                   re.IGNORECASE) is not None:
          return True
      return False

   ## Check if option existed
   # @param optname [in] is a string
   # @return True if optname exists else False
   # @pre parse() returned successfully
   # @todo: XXX change to dict.has_key()
   def _optionExists(self,
                     optname):
      return self._avp.has_key(optname)

   ## Parse the xml config file
   # @pre _file contains a well-formed xml text
   # @post contents of xml file exist in _avp
   def Parse(self):
      self._parser = make_parser()
      self._parser.setContentHandler(self)
      self._parser.parse(self._file)

   ## Collect instructions from xml config file for use by testoob
   # @pre self._avp contgains one or more instructions
   # @throw IOError if no instructions were found
   # @return return dictionary of options specific for testoob
   def GetOpts(self):
      if len(self._avp) == 0:
         raise IOError('File contents incomplete or not xml')
      opts = {}
      if self._optionExists('delayMax'):
         opts['interval'] = self._avp['delayMax'].strip()
      if self._getBoolValue('debugOnError'):
         # don't hang process in pdb if not being run interactively
         if not sys.stdin.isatty() or not sys.stdout.isatty():
            opts['debug'] = True
      if self._optionExists('numThreads'):
         opts['threads'] = self._avp['numThreads'].strip()
      if self._optionExists('outputFile'):
         opts['xml'] = self._avp['outputFile'].strip()
      if self._optionExists('randomizeDelay'):
         opts['randomize-delay'] = self._avp['randomizeDelay'].strip()
      if self._getBoolValue('randomizeTestOrder'):
         opts['randomize-order'] = True
      if self._optionExists('repeat'):
         opts['repeat'] = self._avp['repeat'].strip()
      if self._optionExists('specificTests'):
         opts['glob'] = self._avp['specificTests'].strip()
      if self._getBoolValue('stopOnError'):
         opts['stop-on-fail'] = True
      if self._optionExists('timeout'):
         opts['timeout'] = self._avp['timeout'].strip()
      if self._getBoolValue('verbose'):
         opts['verbose'] = True
      if self._getBoolValue('immediateReports'):
         opts['immediate'] = True
      if self._getBoolValue('verboseAsserts'):
         opts['vassert'] = True
      return opts

   ## Setup login info to a given host
   # @param creds [in] is of the form host:port:user:passwd
   # @post self._avp entries updated from string parsed, msg to stdout
   def UpdateCreds(self,
                   creds):
      rgx = re.compile(r'(.*):(.*):(.*):(.*)');
      hdr = rgx.match(creds)
      idx = ('defaultHost', 'defaultPort', 'defaultLogin', 'defaultPasswd')
      if hdr is not None:
         crds = hdr.groups()
         for val in range(len(crds)):
            if len(crds[val]) > 0:
               logging.info("Using " + idx[val] + "=" + crds[val])
               self._avp[idx[val]] = crds[val]

   ## Setup environment variables to login to hostd
   # @pre defaultHost, defaultLogin, defaultPasswd, defaultProtocol
   #      exist in configuration file
   # @param proto [in] protocol type to use
   # @post VHOST, VLOGIN, VPASSWD, VPROTO, VVERS environment variables exist
   def SetConnectionInfo(self,
                         proto,
                         version = None):
      if self._optionExists('defaultHost'):
         os.environ['VHOST'] = self._avp['defaultHost'].strip()
      if self._optionExists('defaultPort'):
         os.environ['VPORT'] = self._avp['defaultPort'].strip()
      if self._optionExists('defaultLogin'):
         os.environ['VLOGIN'] = self._avp['defaultLogin'].strip()
      if self._optionExists('defaultPasswd'):
         os.environ['VPASSWD'] = self._avp['defaultPasswd'].strip()
         
      if proto is None:
         if self._optionExists('defaultProtocol'):
            proto = self._avp['defaultProtocol'].strip()
         else:
            proto = "soap"
      proto = proto.upper()
      if (re.match(r'VMDB|SOAP', proto) is None):
         raise Exception, "Protocol type must be one of vmdb or soap, got: " + str(proto)
      os.environ['VPROTO'] = proto
      logging.info("Connection protocol set to: " + proto)

      if version is None:
         if self._optionExists('defaultVersion'):
            version = self._avp['defaultVersion'].strip()
         else:
            version = "vim2"
      if (re.match(r'vim2|neptune|logan|dev', version) is None):
         raise Exception, "Unknown VMODL Version: " + str(version)
      os.environ['VVERS'] = version
      if proto.lower() == "soap":
         logging.info("Connection VMODL version set to: " + version)
      else:
         logging.info("Connection VMODL version not used (%s)" % (version))
         
   ## Retrieve list of test directories (python modules)
   # @param baseDir [in] if given is checked against each module
   #                name to verify it exists
   # @return list of all case_*.py files found in self._testModules
   # @pre parse() was successful, _testModules exists
   def GetModuleList(self,
                     baseDir=None):
      if not baseDir is None:
         for item in self._testModules:
            tDir = os.path.join(baseDir, item)
            if not os.path.exists(tDir):
               raise IOError("Test Module not found: " + tDir)
            if not os.path.exists(os.path.join(tDir,   "__init__.py")):
               raise IOError("Test Module missing __init__.py")
      fl = []
      rgx = re.compile(r'^case_\d+(.+)?\.py$');
      for ix in self._testModules:
         try:
            path = os.path.join(baseDir, ix)
            for fn in os.listdir(path):
               if rgx.match(fn): # create a string for 'import' cmd
                  fl.append("%s.%s" % (ix, os.path.splitext(fn)[0]))
         except OSError:
            logging.error("Ignoring test directory " + path)
      return fl

## Filter a TestSuite to include only those testnames
# that match a given regex expression applied over
# the names of the class/method
class FilterSuite:
   ## Filter out test cases by regular expression from a test suite
   # @param suite is a class unitTest.testsuite
   # @param regex is a list of regular expressions to filter with
   # @return strip out those tests that do not match regex
   def __init__(self,
                suite,
                regex):
      if suite.countTestCases() == 0:
         logging.warning("No test found after loading config file.")
         return
      if suite is None:
         logging.warning("No regular expression provided.")
         return

      self._suite = unittest.TestSuite()
      self._rgxs = []
      for item in regex:
         self._rgxs.append(re.compile(item))
      self._visitAll(suite)

   ## @pre elem is object to add to dict
   def _addElem(self,
                elem):
      # print "DEBUG: adding " + str(elem)
      self._suite.addTest(elem)

   ## walk all objects in this structure
   # @param cur structure to walk from
   # @pre: _rgxs is a list of expressions to apply
   # NOTE: @todo: XXX make an iterator object, see CollectTests
   def _visitAll(self,
                 cur):
      if cur is None:
         return

      if isinstance(cur, unittest.TestSuite):
         for item in cur._tests:
            try:
               getattr(item, 'addTests') # is this a TestSuite?
               self._visitAll(item)
            except AttributeError:
               # 1. try to match testcase name
               for rgx in self._rgxs:
                  if rgx.match(str(self._normalizeName(item))) \
                         is not None:
                     self._addElem(item)
                     break
               else:  # 2. nope, match against test function name
                  for elem in dir(item):
                     if callable(elem) and elem.startswith('test'):
                        for rgx in self._rgxs:
                           if rgx.match(elem) is not None:
                              self._addElem(item)
                              break
      else:
         # ignore such items
         return

   ## Get a normalized identifier from an unittest.TestCase object
   # @param obj [in] an instance of a TestCase derived object
   # @return string of 'module.file.class.function'
   def _normalizeName(self, obj):
      if hasattr(obj, 'id'):
         return obj.id()
      else:
         return str(obj.__class__)

   ## @return filtered suite constructed from regex, suite passed to ctor
   def GetSuite(self):
      return self._suite


if __name__ == '__main__':
   sys.exit(_Main())
