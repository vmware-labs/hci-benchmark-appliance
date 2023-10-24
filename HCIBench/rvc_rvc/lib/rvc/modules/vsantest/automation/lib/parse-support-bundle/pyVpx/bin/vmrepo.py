#!/usr/bin/python
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential

##  @file vmrepo.py --
#  @brief Purpose: Install and maintain a set of test VMs on a specified system.
#         Update vmInventory.xml with these test VMs as necessary
#  Compatibility: Python 2.2 and up
#  VMware, Inc 2006
# external program dependencies: mkdir, cp, rsync, touch, kill, ps, mgmt-hostd,
#
__author__ = "VMware, Inc"

import os
import os.path
import errno
import sys
import re
import time
from xml.sax import handler, make_parser
from xml.sax.saxutils import XMLGenerator
from xml.sax.saxutils import escape
import traceback
import shutil
import ConfigParser


## Verify and/or create a directory path
# from holger@trillke.net 2002/03/18
# @param path [in] path to verify/create
def _MkPath(path):
   dpath = os.path.normpath(os.path.dirname(path))
   if not os.path.exists(dpath):
      os.makedirs(dpath)
   return os.path.normpath(os.path.abspath(path))

## Determine where to store tests VMs by platform
# @return destdir a writeable directory to store vms in
# TODO: this could be made more exact, check for minimal storage needed
def _FetchDestinationDir():
   dirp = None
   if os.path.exists(os.path.abspath('c:\\')):
      dirp = 'c:\\temp'   # TODO: temp location on windows
   else:
      vmfs = '/vmfs/volumes'
      if os.path.exists(vmfs):
         for item in os.listdir(vmfs):
            if os.path.isdir(os.path.join(vmfs, item)):
               dirp = os.path.abspath(os.path.join(vmfs,item))
               break
   if dirp is None:
      raise Exception("Can't guess where to store VM data files, use -t option or set vmrepo.cfg")
   if not os.path.exists(dirp):
      raise Exception(dirp + " does not exist, use -t option or set vmrepo.cfg")
   dirp = os.path.join(dirp, "testvms")
   try:
      _MkPath(dirp)
   except Exception, msg:
      raise Exception("Create/Verify directory:" + \
                      dirp + " reason: " + str(msg))
   print "INFO: Test VMs located in " + dirp
   return dirp

## vmInventory.xml file used by hostd to keep track of vms on disk
# @pre os.uname() returns either Linux or CYGWIN_*
# @return fully qualified path to vmInventory.xml
def _FetchInventoryFile():
   osn = sys.platform
   if osn == 'linux2':
      if os.path.exists('/vmfs'):  #ESX
         return  '/etc/vmware/hostd/vmInventory.xml'
      else:                        #hosted TODO:
         return '/etc/vmware/hostd/vmInventory.xml'
      return
   elif osn == 'win32':
      return os.path.join("c:\\", "vmInventory.xml")
   else:
      raise Exception, "Unsupported OS " + osn

## Return the path the shell script to control hostd
# @param installed [in] if True use installed program else use source tree
# @return path to mgmt script
def _FetchMgmtScript(installed=True):
   osn = sys.platform
   if osn == 'linux2':
      if installed is True:
         return "/etc/init.d/mgmt-vmware"
      else:
         return "./mgmt-hostd"
   elif osn == 'win32':
      if installed is True:
         # TODO: use wmi module to get installed mgmt script
         raise Exception("Use installed not supported yet")
      else:
         return os.path.join("./", "mgmt-hostd")
   else:
      raise Exception, "Unsupported OS " + osn

## create an empy vmInventory file
# @post fileName exists on filesystem
# @throw Exception if file can not be created
def _CreateVmInventory(fileName):
   tfp = None
   try:
      try:
         tfp = file(fileName, "w")
         tfp.write("<ConfigRoot></ConfigRoot>")
      except Exception, msg:
         raise Exception("open or write to file: " + fileName + \
                         ", failed: " + str(msg))
   finally:
      if tfp is not None:
         tfp.close()

## find out where hostd 'config.xml' and mgmt-* scripts are
# @return tuple of: fully qualified path to vmInventory.xml, and
#         path to 'mgmt-hostd' script
# @throw Exception if config file does not exist
def _InitInventoryAndMgmtScript(opts):
   if opts.use_default is True:
      mgmt = _FetchMgmtScript(True)
      cfile = _FetchInventoryFile()
   else:
      mgmt = _FetchMgmtScript(False)
      cfgf = _GetCfgFile()
      sc = SoloConfig(cfgf)
      if sc.vmInventory is None:
         cfile = _FetchInventoryFile()
      else:
         print "INFO: from %s using vmInventory at %s" % \
               (cfgf, sc.vmInventory)
         cfile = sc.vmInventory

   return (cfile, mgmt)

## main entry point for this program to operations to manage VM Test depot
# @return 0 on sucess, 1 on filure
def _Main():
   opts = None
   try:
      opts = _ParseArgs()
      if opts.debug:
         import pdb
         pdb.set_trace()
      if opts.test:
         return _UnitTest()
      # Some validation...
      if not os.access(opts.mgmt, os.X_OK):
         print "ERROR: \'%s\' not found or not executable." % (opts.mgmt)
         return 1
      if not os.path.isfile(opts.config):
         print "ERROR: \'%s\' file not found or accessible." % (opts.config)
         return 1
      repo = VmRepo(opts.depot, opts.config, opts.mgmt, opts.destdir)
      if opts.dry_run:
         repo.Simulate()
      if opts.list:
         rc = repo.List()
         if rc != 0:
            print "ERROR: list Test VM depot failed."
            return 1
      elif opts.sync:
         rc = repo.Sync()
         if rc != 0:
            print "ERROR: Copy and register Test VM depot failed."
            return 1
      elif opts.clean:
         rc = repo.Clean()
         if rc != 0:
            print "ERROR: Unregister and delete Test VM directory failed."
            return 1
      else:
         print "SETTINGS: config:" + opts.config + " mgmt:" + opts.mgmt + " destdir:" + opts.destdir + " depot:" + opts.depot
         print "USAGE: Must specify --list, --sync, or --clean, see --help"
         return 1
   except SystemExit:
      return 1
   except Exception, msg:
      print "ERROR: " + str(msg)
      if opts is not None and opts.debug:
         print traceback.print_exc()
      return 1

## @return the hostd config file which contains hostd vmInventory file path
def _GetCfgFile():
   cmd = "./mgmt-hostd showcfg"
   osn = sys.platform
   if osn == 'linux2':
      pass
   elif osn == 'win32':
      cmd = "sh " + cmd
   else:
      raise Exception, "Unsupported OS " + osn

   result = os.popen(cmd).readlines()
   if not result:
      raise Exception("cmd failed: " + cmd)
   fn = result[0].strip()
   if not os.path.exists(fn):
      raise Exception(cmd + " -- returned invalid filename: '" + fn + "'")
   if not os.access(fn, os.R_OK):
      raise Exception(fn + " can not be read from.")
   return fn

## Return location store temporary files
# @return path to a writeable directory
def _GetTmpDir():
   osn = sys.platform
   if osn == 'linux2': return "/tmp"
   elif osn == 'win32':
      if os.environ.has_key('TEMP'):
         if os.path.exists(os.environ['TEMP']):
            return os.environ['TEMP']
      else:
         return "c:/temp"
   else:
      raise Exception, "Unsupported OS " + osn

## Specify where a dummy test xml file resides
# @return a fully qualified path to a test vmInventory in the temp directory
def _GetTestInvFile():
   fn = 'vmInventory.Test.xml'
   return os.path.join(_GetTmpDir(), fn)

## Verify the class VmInventory (and sax parser) works using a made up xml file
# @return 0 on success 1 on failure
def _UnitTest():
   print "Create vmInventory Object"
   tf = _GetTestInvFile()
   if os.path.exists(tf):
      os.unlink(tf)
   _CreateVmInventory(tf)
   vx = VmInventory(tf, False, None)
   print "List"
   vx.List()
   print "AddEntries"
   vx.AddEntries(['/a/b/c', '/d/e/f/'])
   print "List"
   vx.List()
   print "RemoveEntries"
   vx.RemoveEntries(['/a/b/c', '/d/e/f/'])
   vx.List()
   df = open(tf,"r")
   try:
      result = df.read()
   finally:
      df.close()
   pattern = r"\s*<\?xml.*>\s*<ConfigRoot></ConfigRoot>\s*"
   if re.match(pattern, result) is not None:
      print "INFO: PASS test "
   else:
      print "INFO: FAIL test results match"
      print "EXPECTED:",
      print pattern
      print "RECEIVED:",
      print result
      return 1
   os.unlink(tf)
   return 0

## update opts with values from config file if any
# @param opts [in/out] values for program execution
# @pre vmrepo.cfg file exists, and parses ok
# @post opts contains values from config file only
#       if not already set
def _SetDefaults(opts):
   try:
      cfg = Config("vmrepo.cfg")
      dd = "depot"
      if opts.depot is None:
         opts.depot = cfg.get("vmrepo", dd)
      dd = "destdir"
      if opts.destdir is None:
         opts.destdir = cfg.get("vmrepo", dd)
      dd = "config"
      if opts.config is None:
         opts.config = cfg.get("vmrepo", dd)
      dd = "mgmt"
      if opts.mgmt is None:
         opts.mgmt = cfg.get("vmrepo", dd)
   except:
      pass
   # Now setup default values if no cmd line or cfg file
   if opts.depot is None:
      fsDepot = "/exit26/home/ha"
      # TODO: switch to IT provided rsync server
      netDepot = "rsync://mrm-esx.eng.vmware.com"
      if not os.path.exists(fsDepot):
         opts.depot = netDepot
      else:
         opts.depot = fsDepot
   if opts.destdir is None:
      opts.destdir = _FetchDestinationDir()
   (cfile, mgmt) = _InitInventoryAndMgmtScript(opts)
   if opts.mgmt is None:
      opts.mgmt = mgmt
   if opts.config is None:
      opts.config = cfile


## @return an object containing parsed command line options
def _ParseArgs():
   try:
      import optparse
   except ImportError:
      from testoob.compatibility import optparse
   usage = """usage: %prog [options]
   defaults:
   config = Linux: '/etc/vmware/hostd/vmInventory.xml'
            Win32: 'c:/vmInventory.xml'
   depot = { Linux|Win32: 'rsync://mrm-esx.eng.vmware.com/testvm' }
   """
   formatter = optparse.TitledHelpFormatter(max_help_position=30)
   popt = optparse.OptionParser(usage=usage, formatter=formatter)
   popt.add_option("-l", "--list", action="store_true",
                   help="list Test VMs in depot")
   popt.add_option("-s", "--sync", action="store_true",
                   help="sync Test VM depot to this machine")
   popt.add_option("-c", "--clean", action="store_true",
                   help="clean out Test VMs on this machine")
   popt.add_option("-f", "--config", action="store", type="string", dest="config",
                   help="specify xml config file to modify")
   popt.add_option("-t", "--destdir", action="store", type="string", dest="destdir",
                   help="specify filesystem path to place test VMs")
   popt.add_option("-p", "--depot", action="store", type="string", dest="depot",
                   help="specify rsync depot to use")
   popt.add_option("-m", "--mgmt", action="store", type="string", dest="mgmt",
                   help="specify mgmt script to start/stop hostd, \
                   default is ./mgmt-hostd, if -b then system installed: /etc/init.d/mgmt-hostd")
   popt.add_option("-n", "--dry-run", action="store_true",
                   help="Display what cmds would be run")
   popt.add_option("-b", "--use-default", action="store_true",
                   help="Use system default vmInventory.xml and hostd start/stop script")
   popt.add_option("-d", "--debug", action="store_true",
                   help="step trace this program")
   popt.add_option("-u", "--test", action="store_true",
                                       help="run self test")
   options, parameters = popt.parse_args()
   options.params = parameters  # hackish, modify object to return parameters
   # load any unset values from a config file, if any
   _SetDefaults(options)
   # TODO: this may need to be per product or platform?
   if options.depot.startswith("rsync:"):
      options.depot = options.depot +  "/testvm"
   else:
      options.depot = os.path.join(options.depot, "testvm")
   sys.argv = [sys.argv[0], sys.argv[-1]]
   return options

## Run a Subcommand using system shell
# Supports two modes of execution: echo the cmd to run
# or invoke the actual command
class SubCommand:
   def __init__(self):
      self._echoOnly = False
   def EchoOn(self):
      self._echoOnly = True
   def EchoOff(self):
      self._echoOnly = False
   def IsEchoOn(self):
       return self._echoOnly
   ## @param userCmd [in] is a string
   # @post no change to this objects state
   # @return results of system call returned
   def Invoke(self,
              userCmd):
      sys.stdout.flush()
      if self._echoOnly:
         cmd = "echo " + userCmd
      else:
         cmd = userCmd
      return os.system(cmd)

## A sax based parser to pick out various settings from solo plugin config
# like vmInventory (no matter where found in the config file)
class SoloConfig(handler.ContentHandler):
   ## @param file [in] is a path to an xml config file
   def __init__(self,
                file):
      if file is None:
         raise Exception("Specify name of solo.xml to read intead of None")
      if not os.path.exists(file):
         raise Exception("File not accessible: " + file)
      handler.ContentHandler.__init__(self)
      self._parser = make_parser()
      self._parser.setContentHandler(self)
      self._parseState = []
      try:
         self._parser.parse(file)
      except IOError, msg:
         print "ERROR: reading file: \"" + file + "\" " + str(msg)
         raise
      self.vmInventory = None

   ## @post Remove redundant whitespace from a string
   def _fixWhitespace(self,
                      text):
      return ''.join(text.split())

   def startElement(self,
                    name,
                    attrs):
      self._data = ""
      self._parseState.append(self._fixWhitespace(name))

   def endElement(self,
                  name):
      fn = self._fixWhitespace(name)
      if fn == 'vmInventory':
         self.vmInventory = self._fixWhitespace(self._data)
      self._parseState.pop()

   def characters(self,
                  info):
      self._data += info

##
# Retrieve options from config file
class Config:
   def __init__(self, fname):
      self._cf = None
      self._fname = fname
      try:
         ff = open(fname, "r")
         try:
            cf = ConfigParser.ConfigParser()
            cf.readfp(ff, filename=fname)
         finally:
            ff.close()
      except ConfigParser.ParsingError, msg:
         print "WARNING: ignoring invalid config file: " \
               + fname + " reason:" + str(msg)
      except:
         raise Exception, "Config file not processed"
      self._cf = cf

   ## retrieve option from config
   # @param sect [in] section to search
   # @param opt [in] opt to fetch
   # @return None or string value
   # @throw Exception if object did not read the config file
   def get(self, sect, opt):
      if self._cf is None:
         raise Exception, "Invalid config file: " + self._fname
      try:
         return self._cf.get(sect, opt)
      except ConfigParser.NoOptionError:
         pass
      return None

## Manage the vmInventory xml data file
# Reads an vmInventory config file which consists of zero one or more:
#     <ConfigRoot>
#          <ConfigEntry id="0001">
#             <objID>39808</objID>
#             <vmxCfgPath>/vmfs/volumes/storage1/SUSP1/SUSP1.vmx</vmxCfgPath>
#          </ConfigEntry>
#      </ConfigRoot>
class VmInventory(handler.ContentHandler):
   ## @param file [in] is xml file to load in
   # @param testMode [in] if true, no changes are made to system
   # @param mgmtScript [in] is used to determine which hostd to manipulate
   def __init__(self,
                file,
                testMode=False,
                mgmtScript='/etc/init.d/mgmt-vmware'):
      handler.ContentHandler.__init__(self)
      self._parser = make_parser()
      self._parser.setContentHandler(self)
      self._cfgFile = file
      self._dirty = True
      self._testMode = testMode
      self._mgmtScript = mgmtScript
      self._parseFile()
      self._scmd = SubCommand()

   ## @pre self._cfgFile exists and contains xml data
   # @post self._entries matches data in _cfgFile
   def _parseFile(self):
      if not os.path.exists(self._cfgFile):
         raise Exception("File not accessible: " + self._cfgFile)
      self._parseState = []
      # these three items represent current ConfigEntry values parsed
      self._path = None
      self._id = None
      self._objID = None
      # store values as key: vmxCfgPath data:[objid, id]
      self._entries = {}
      try:
         try:
            fp = open(self._cfgFile)
         except Exception, msg:
            raise Exception("open file \"%s\" failed %s" % \
                            (self._cfgFile, str(msg)))
         try:
            self._parser.parse(fp)
         except Exception, msg:
            raise Exception( \
               "parse xml file \"%s\" failed %s" % (self._cfgFile, str(msg)))
      finally:
         fp.close()
      self._dirty = False

   ## @return text w/o redundant whitespace
   def _fixWhitespace(self,
                      text):
      return ''.join(text.split())

   def startElement(self,
                    name,
                    attrs):
      self._data = ""
      self._name = self._fixWhitespace(name)
      self._parseState.append(self._name)
      val = attrs.get('id', None)
      if (val is not None):
         if self._id is not None:
            raise Exception( \
               "invalid xml data file, seen two id= attrs:" + self._id)
         self._id = self._fixWhitespace(val)

   def endElement(self,
                  name):
      if len(self._parseState) > 2 and self._parseState[-2] == "ConfigEntry":
         if name == 'objID':
            if self._objID is not None:
               raise Exception("invalid xml data file, seen two objID:" \
                               + self._objID)
            self._objID = self._fixWhitespace(self._data)
         else:
            if name == 'vmxCfgPath':
               if self._path is not None:
                  raise Exception( \
                     "invalid xml data file, seen two vmxCfgPath:" + self._path)
               self._path = self._fixWhitespace(self._data)
         if self._path is not None and \
                self._objID is not None and self._id is not None:
            if self._entries.has_key(self._path) is True:
               raise Exception(\
                  "invalid xml data file, seen two vmxConfigPath entries:" + \
                               self._path)
            self._entries[self._path] = [self._objID, self._id]
            self._path = None
            self._id = None
            self._objID = None
            self._name = None
            self._data = ""
      self._parseState.pop()

   def characters(self,
                  info):
      self._data += info

   ## Add a new vm entry to the inventory xml config file
   # @param entrySet [in] is a list of vmx files paths
   # @post cfg file updated with list (no duplicate vmx paths)
   def AddEntries(self,
                  entrySet):
      # cull out duplicates if any
      dups = []
      for item in entrySet:
         if self._entries.has_key(item):
            dups.append(item)
      if len(dups) > 0:
         print "INFO: " + str(len(dups)) + " entries already exist, skipping."
         for item in dups:
            idx = entrySet.index(item)
            del entrySet[idx]
      del dups
      if len(entrySet) == 0:
         print "INFO: Nothing to add to file: " + self._cfgFile
         return
      # write out a new file and rename old one
      done = False
      nfn = self._cfgFile + ".new"
      xv = self.xmlFile(nfn)
      try:
         # output existing items
         for item in self._entries.keys():
            val = self._entries[item]
            xv.Write(item, val)
         # output new items with unique id, objid values
         val = [0, len(self._entries)]
         for item in entrySet:
            val[0] += 1
            val[1] += 1
            self.FindUnique(val)
            xv.Write(item, val)
         done = True
      finally:
         xv.Close()
      # backup old, install new
      if done is True:
         self.InstallFile(nfn)
         print "INFO: Added " + str(len(entrySet)) + \
               " entries to " + self._cfgFile + "."
      self._dirty = True

   ## Terminate any VM processes running test VMS
   # @post vm processes running TTT*.vmx cfgs are shut down
   def _KillLinuxProcesses(self):
      rx = re.compile(r'.*vmware-vmx.*/testvms/TTT.*\.vmx')
      cnt = 0
      pids = []
      proc = '/proc'
      files = []
      for pd in os.listdir('/proc/'):
         if re.match(r'[0-9]+', pd) is None:
            continue
         fp = os.path.join(proc, pd)
         if os.path.isdir(fp):
            files.append(os.path.join(fp, "cmdline"))
      for item in files:
         try:
            fp = open(item.strip())
            line = fp.read()
            if line != "":
               match = rx.search(line)
               if match is not None:
                  pids.append(os.path.basename(os.path.dirname(item)))
                  cnt += 1
                  fp.close()
         except:
            pass

      if len(pids) > 0:
         pl = "".join(["%s " % (ix) for ix in pids])
         cmd = "kill -SIGHUP %s" % (pl)
         rc = os.system(cmd)
         if (rc >> 8) != 0:
            raise Exception("cmd %s failed" % (cmd))
      print "INFO: Killed %d vmware-vmx processes" % cnt
      # yield back to processor for cleanup
      if cnt > 0:
         time.sleep(1)

   ## Shutdown/kill off any VMX processes running test VMS
   #
   def _KillWin32Processes(self):
      try:
         import wmi11.wmi
      except:
         print \
"WARNING: wmi.py not installed test VM (vmx) processes need manual shutdown."
         return
      cr = wmi11.wmi.WMI()
      for process in cr.Win32_Process(Name="vmware-vmx.exe"):
         if process.CommandLine.find("TTTVM") > 0:
            result = process.Terminate()
            if result is not None and result[0] != 0:
               print "ERROR: terminate process: " + str(process.ProcessId) + \
                     " failed: " + str(result)


   ## @post any vms found in testvms/TTT* are sent kill signal
   # report to stdout how many processes were sent kill -HUP
   def KillTestVMProcesses(self):
      osn = sys.platform
      if osn == 'linux2': self._KillLinuxProcesses()
      elif osn == 'win32': self._KillWin32Processes()
      else:
         raise Exception, "Unsupported OS " + osn

   ## @param nfn [in] is new file to install
   # @post: orig file is backed up to /tmp, new file replaced existing
   def InstallFile(self,
                   nfn):
      tmpf = _GetTmpDir()
      fnf = "%s.%s" % (os.path.basename(self._cfgFile), str(os.getpid()))
      bkf = os.path.join(tmpf, fnf)
      print "INFO: Backup " + self._cfgFile + " to " + bkf
      try:
         shutil.copyfile(self._cfgFile, bkf)
      except Exception, msg:
         raise Exception("Backup %s to %s failed: %s" % \
                         (self._cfgFile, bkf, str(msg)))
      restart = False
      self.KillTestVMProcesses()

      if self._IsHostdRunning() is True:
         print "INFO: shutting down hostd, manual restart is required."
         if self._mgmtScript is not None:
            restart = True
            cmd = self._mgmtScript + ' stop'
            if self._scmd.Invoke(cmd) != 0:
               raise Exception("cmd failed:" + cmd)
      if not self._testMode:
         try:
            self._ReplaceFile(nfn, self._cfgFile)
         except Exception, msg:
            msg = "os.rename %s to %s failed %s" % \
                  (nfn, self._cfgFile, str(msg))
            raise Exception, msg
      if restart is True:
         if self._mgmtScript is not None:
            cmd = self._mgmtScript + ' start'
            if self._scmd.Invoke(cmd) != 0:
               raise Exception("cmd failed:" + cmd)

   ## replace contents of old file with new file
   # @param newFile [in] the name of the file containing new data
   # @param oldFile [out] name of file whose contents will be replaced
   # @throw Exception on error case
   def _ReplaceFile(self, newFile, oldFile):
      if sys.platform == 'win32' and os.path.exists(oldFile):
         # POSIX rename does an atomic replace, WIN32 rename does not.
         try:
            os.remove(oldFile)
         except OSError, exc:
            if exc.errno != errno.ENOENT:
               raise exc
      os.rename(newFile, self._cfgFile)

   ## Check OS process list to see if the right instance of hostd is running
   # @pre self._mgmtScript exists
   # @post return True if vmware-hostd is running else False
   def _IsHostdRunning(self):
      found = False
      if self._mgmtScript is None:
         print "WARNING: hostd control script not specified, assume down"
         return found
      print "INFO: Using hostd script: %s " % (self._mgmtScript)
      cmd = self._mgmtScript + " status"
      result = os.popen(cmd).readlines()
      if len(result) > 0:
         if re.search(r'vmware\-host.*is running', result[0],
                      re.IGNORECASE) is not None:
            print result[0].strip()
            found = True
      return found

   ## @param ids [in] contains [objid, id] pair
   # @post ids updated with values not currently in use
   def FindUnique(self,
                  ids):
      # find unique objid
      idx = 0
      iv = ids[idx]
      done = False
      while done is False:
         done = True
         for item in self._entries.values():
            if iv == item[idx]:
               iv += 1
               done = False
      ids[idx] = iv
      # find unique id
      idx += 1
      iv = ids[idx]
      done = False
      while done is False:
         done = True
         for item in self._entries.values():
            if iv == item[idx]:
               iv += 1
               done = False
      ids[idx] = iv

   ## @param entrySet [in] is a list of vmx files paths
   # @post: cfg file updated, entrySet items removed
   def RemoveEntries(self,
                     entrySet):
      if len(entrySet) == 0:
         return
      # write out a new file and rename old one
      done = False
      nfn = self._cfgFile + ".new"
      xv = self.xmlFile(nfn)
      ctr = 0
      try:
         for item in self._entries.keys():
            if item in entrySet:
               ctr += 1
               pass
            else:
               val = self._entries[item]
               xv.Write(item, val)
         done = True
      finally:
         xv.Close()
      # backup old, install new
      if done is True:
         self.InstallFile(nfn)
         print "INFO: Removed " + str(ctr) + " entries from " + self._cfgFile + "."
      self._dirty = True

   ## @pre entrySet is a list of vmx files paths
   # @post cfg file updated with list (no duplicates)
   def List(self):
      if (self._dirty):
         self._parseFile()
      if len(self._entries) == 0:
         print "INFO: No VMs are registered"
      else: # assume we read in pairs...
         for item in self._entries.keys():
            val = self._entries[item]
            print "VM: ID=" + val[1] + " OBJID=" + val[0] + " CFG=" + item

   ## Generate file containing xml using vmInventory schema
   # as observed frm esx 3.0
   class xmlFile:
      def __init__(self,
                   filename):
         self._fp = open(filename, 'w')
         self._xg = XMLGenerator(self._fp)
         self._xg.startDocument()
         self._xg.startElement(u'ConfigRoot', {})

      def Write(self,
                item,
                val):
         attrs = {'id' : "%04i" % (int(val[1])) }
         self._xg.startElement(u'ConfigEntry', attrs)
         self._xg.startElement(u'objID', {})
         self._xg.characters(str(val[0]))
         self._xg.endElement(u'objID')
         self._xg.startElement(u'vmxCfgPath', {})
         self._xg.characters(escape(item).encode('UTF-8'))
         self._xg.endElement(u'vmxCfgPath')
         self._xg.endElement(u'ConfigEntry')

      def Close(self):
         self._xg.endElement(u'ConfigRoot')
         self._xg.endDocument()
         self._fp.close()

## The VM Depot API
# It keeps a set of Virtual Machine files on a host under test
# in sync with a master depot. By default it assumes installed
# hostd is instance to integrate with
class VmRepo:
   ## Initialize PATH to KROOT/bin for rsyc
   # @param srcRepo [in] uri to rsync depot
   # @param cfgFile [in] hostd's vmInventory.xml
   # @param mgmtScript [in] interface to hostd
   # @param destDir [in] path to where VMs are stored
   def __init__(self,
                srcRepo,
                cfgFile,
                mgmtScript,
                destDir=None):
      self._src = srcRepo
      self._mgmtScript = mgmtScript # interface: vmware-hostd start|stop
      self.destDir = destDir # filesystem location where to place testvms/...
      self._scmd = SubCommand()

      # where to find rsync?
      pgm = self._FindToolchainRsync()
      if not os.path.exists(pgm):
         raise Exception("Program not found: '" + pgm + "'")
      self._rsync = pgm

      self._cfgFile = cfgFile

   ## Return path to rsync in toolchain directory
   # @return fully qualified path to rsync binary
   def _FindBoraRootRsync(self):
      if sys.platform == 'linux2':
         return '/build/toolchain/lin32/rsync-2.6.9/bin/rsync'
      elif sys.platform == 'win32':
         return r'%s\win32\cygwin-1.5.19-4\bin\rsync.exe' % os.environ['TCROOT']
      else:
         raise Exception, "Unsupported OS " + sys.platform
   ## Get the rsync binary file name
   # @pre sys.platform is either: win32 or linux2
   # @return filename of rsync binary
   def _GetRsyncBinaryName(self):
      osn = sys.platform
      if osn == 'linux2': return "rsync"
      elif osn == 'win32': return "rsync.exe"
      else:
         raise Exception, "Unsupported OS " + osn

   ## @post all system calls have echo added to them before execution
   def Simulate(self):
      self._scmd.EchoOn()

   ## List Test VMs installed in this registry
   # @return 0 on success 1 on error
   # TODO: fetch descr.xml and dump that as well
   def List(self):
      pr = VmInventory(self._cfgFile, self._scmd.IsEchoOn(), self._mgmtScript)
      print "INFO: File " + self._cfgFile +  " contains these VMs"
      pr.List()
      print "INFO: Depot (" + self._src+  ") contains these VMs"
      cmd = "%s %s" % (self._rsync, self._src)
      self._scmd.Invoke(cmd)
      return 0

   ## @pre about to modify vmInventory
   # @return True if this is safe/possible to do else False
   #         and msg to stdout
   def _preCheck(self):
      osn = sys.platform
      if osn == 'linux2':
         if (os.geteuid() != 0):
            print "ERROR: Must have root privilege"
            return False
      elif osn == 'win32':
         # TODO: must have administrator priv? use wmi module
         pass
      else:
         raise Exception, "Unsupported OS " + osn
      return True

   ## sync VM depot with this system
   # The local directory is determined automagically
   # @return 0 on success else 1 on error
   # TODO: better directory selection + space checking?
   # TODO: on success, place cookie on system where we put it last
   def Sync(self):
      if self._preCheck() is False:
         return 1
      iv = VmInventory(self._cfgFile, self._scmd.IsEchoOn(), self._mgmtScript)
      iv.KillTestVMProcesses()
      del iv

      # display eye-candy else just report stats in output log
      if sys.stdin.isatty() and sys.stdout.isatty():
         rptFlag = "--progress"
      else:
         rptFlag= "--stats"
      cmd = "%s %s -rStpL --delete %s/* %s" % \
            (self._rsync,  rptFlag, self._src, self.destDir)
      rc = self._scmd.Invoke(cmd)
      if rc != 0:
         raise Exception("failed cmd: " + cmd)
      self._registerTestVMs()
      return rc

   ## Unregister and delete the Test VM depot on this system
   # @return 0 on success else 1 on error
   # TODO: better directory selection + space checking?
   def Clean(self):
      if self._preCheck() is False:
         return 1
      if not os.path.exists(self.destDir):
         print "INFO: Test VMs not loaded in: " + self.destDir
         return 0

      self._unregisterTestVMs()
      if not os.path.exists(self.destDir):
         print "WARNING: Test VM Depot not found in " + self.destDir
         return 0
      print "INFO: Removing the directory and contents of " + self.destDir
      shutil.rmtree(self.destDir, self._ReportRmErrs)
      if os.path.exists(self.destDir):
         print "failed to remove subdir:" + self.destDir
         return 1
      return 0

   ## Part of vm tree removal process, dump msgs to stdout
   #
   def _ReportRmErrs(self, func, path, excinfo):
      print "ERROR: %s(%s) failed %s" % (str(func), path, str(excinfo))

   ## @pre TestVMs exist in hostd registry
   # @post TestVMs are removed from hostd registry
   def _unregisterTestVMs(self):
      if (self._scmd.IsEchoOn()):
         return
      try:
         vmxs = self._gatherVMXFiles()
         if len(vmxs) > 0:
            print "INFO: Removing Test VMs from " + self._cfgFile
            pr = VmInventory(self._cfgFile, self._scmd.IsEchoOn(),
                             self._mgmtScript)
            pr.RemoveEntries(vmxs)
      except Exception, msg:
         msg = "using " + self._cfgFile + " failed " + str(msg)
         raise Exception(msg)

   ## @pre self.destDir contains test VMs to register
   # @post self._cfgFile contains added vms
   def _registerTestVMs(self):
      if (self._scmd.IsEchoOn()):
         return
      vmxs = self._gatherVMXFiles()
      if len(vmxs) > 0:
         try:
            print "INFO: Adding Test VMs to " + self._cfgFile
            pr = VmInventory(self._cfgFile, self._scmd.IsEchoOn(),
                             self._mgmtScript)
            pr.AddEntries(vmxs)
         except Exception, msg:
            msg = "using " + self._cfgFile + " failed " + str(msg)
            raise Exception(msg)
      else:
         print "WARNING: no *.vmx files found to register"

   ## @pre self.destDir is set
   # @post no changes to this object
   # @return a list of paths to *.vmx files under destDir or []
   def _gatherVMXFiles(self):
      vmxs = []
      for vdr in os.listdir(self.destDir):
         path = os.path.join(self.destDir, vdr)
         if os.path.isdir(path):
            for fn in os.listdir(path):
               if re.match(r'.*\.vmx$', fn, re.IGNORECASE) is not None:
                  vmxs.append(os.path.realpath(os.path.join(path, fn)))
      return vmxs

if __name__ == '__main__':
   sys.exit(_Main())
