#!/usr/bin/python

#
# Basic tests for Vim::Vm::Guest::FileManager
#
# These require the latest tools on a VM with a supported guest
#
from __future__ import print_function

from pyVmomi import Vim, Vmodl
from pyVim.helpers import Log
from pyVim import arguments
from datetime import datetime
from urlparse import urlparse
from httplib import HTTPSConnection;
import httplib, urllib;
from guestOpsUtils import *
import unittest

def waitForProcessToComplete(virtualMachine, guestAuthentication, pid):
   pids = [pid]
   while True:
      Log("Waiting for process %s to complete" % pid)
      time.sleep(3)
      result = procMgr.ListProcesses(virtualMachine, guestAuthentication, pids)
      process = result.pop()
      if process.endTime:
         Log("Process completed with exit code: %s" % process.exitCode)
         break

def startProgramEx(virtualMachine, guestAuthentication, programPath, workingDirectory, arguments):
   Log("Start program %s %s" % (programPath, arguments))
   spec = procDef.ProgramSpec(programPath=programPath, workingDirectory=workingDirectory, arguments=arguments)
   pid = procMgr.StartProgram(virtualMachine, guestAuthentication, spec)
   waitForProcessToComplete(virtualMachine, guestAuthentication, pid)
   return pid

def generateStringWithSpecifiedSize(size):
   return "0" * size;

def testSetup():
   global baseDir

   result = procMgr.ReadEnvironmentVariable(virtualMachine, guestAuth, "HOME")
   if len(result) != 1:
      raise Exception ("Failed to fetch $HOME env var")
   home = (result[0].split('='))[1]
   Log("Fetched $HOME for guestuser: " + home)

   baseDir = home + "/guestFileManagerTests/"
   try:
      Log("Cleaning up test workspace if any")
      result = fileMgr.DeleteDirectory(virtualMachine, guestAuth, baseDir, True)
   except:
      pass

   Log("Setting up test workspace")
   result = fileMgr.MakeDirectory(virtualMachine, guestAuth, baseDir, False)
   Log("Created baseDir for guestFileManagerTests: " + baseDir)


def createFile(path):
   arg = "> " + path
   result = startProgramEx(virtualMachine, guestAuth, "/bin/ls", baseDir, arg)

def createEmptyFile(path):
   startProgramEx(virtualMachine, guestAuth, "/bin/touch", baseDir, path)


class TestCase(unittest.TestCase):
   def setUp(self):
      self.testDir = baseDir + self.__class__.__name__ + "/";
      fileMgr.MakeDirectory(virtualMachine, guestAuth, self.testDir, False)

   def tearDown(self):
      fileMgr.DeleteDirectory(virtualMachine, guestAuth, self.testDir, True)


class MakeDirectoryErrorAlreadyExists(TestCase):

   def runTest(self):
      dirPath = self.testDir
      recursive = False
      with self.assertRaises(Vim.Fault.FileAlreadyExists):
         fileMgr.MakeDirectory(virtualMachine, guestAuth, dirPath, recursive)

class MakeDirectoryRecursive(TestCase):

   def runTest(self):
      dirPath = self.testDir + "dir-1/dir-2"
      recursive = True
      fileMgr.MakeDirectory(virtualMachine, guestAuth, dirPath, recursive)

class MakeDirectoryNonRecursive(TestCase):

   def runTest(self):
      dirPath = self.testDir + "dir-2"
      recursive = False
      fileMgr.MakeDirectory(virtualMachine, guestAuth, dirPath, recursive)

class MakeDirectoryParentNotExisting(TestCase):

   def runTest(self):
      dirPath = self.testDir + "non-existing-dir-1/non-existing-dir-2"
      recursive = False
      with self.assertRaises(Vim.Fault.FileNotFound):
         fileMgr.MakeDirectory(virtualMachine, guestAuth, dirPath, recursive)

class MakeDirectoryErrorNameTooLong(TestCase):

   def runTest(self):
      baseName = ''
      for num in xrange(10):
         baseName += "abcdefghijklmnopqrstuvwxyz0123456789"
      dirPath = self.testDir + baseName
      recursive = False
      with self.assertRaises(Vim.Fault.FileNameTooLong):
         fileMgr.MakeDirectory(virtualMachine, guestAuth, dirPath, recursive)


class DeleteFileExisting(TestCase):

   def setUp(self):
      super(DeleteFileExisting, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      fileMgr.DeleteFile(virtualMachine, guestAuth, self.file)

class DeleteFileErrorNonExisting(TestCase):

   def runTest(self):
      file = self.testDir + "non-existing-file.txt"
      with self.assertRaises(Vim.Fault.FileNotFound):
         fileMgr.DeleteFile(virtualMachine, guestAuth, file)

class DeleteFileErrorNonAFile(TestCase):

   def setUp(self):
      super(DeleteFileErrorNonAFile, self).setUp()
      self.emptyDirPath = self.testDir + "emptyDirectory-1/"
      result = fileMgr.MakeDirectory(virtualMachine, guestAuth, self.emptyDirPath, True)

   def runTest(self):
      with self.assertRaises(Vim.Fault.NotAFile):
         fileMgr.DeleteFile(virtualMachine, guestAuth, self.emptyDirPath)


class DeleteDirectoryErrorNotADirectory(TestCase):

   def setUp(self):
      super(DeleteDirectoryErrorNotADirectory, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      recursive = False
      with self.assertRaises(Vim.Fault.NotADirectory):
         fileMgr.DeleteDirectory(virtualMachine, guestAuth, self.file, recursive)

class DeleteDirectoryErrorNotExisting(TestCase):

   def runTest(self):
      dirPath = self.testDir + "nonExistingDirectory"
      recursive = False
      with self.assertRaises(Vim.Fault.FileNotFound):
         fileMgr.DeleteDirectory(virtualMachine, guestAuth, dirPath, recursive)

class DeleteDirectoryNonRecursive(TestCase):

   def setUp(self):
      super(DeleteDirectoryNonRecursive, self).setUp()
      self.dirPath = self.testDir + "emptyDirectory-1/"
      result = fileMgr.MakeDirectory(virtualMachine, guestAuth, self.dirPath, True)

   def runTest(self):
      recursive = False
      fileMgr.DeleteDirectory(virtualMachine, guestAuth, self.dirPath, recursive)

class DeleteDirectoryErrorNotEmpty(TestCase):

   def setUp(self):
      super(DeleteDirectoryErrorNotEmpty, self).setUp()
      self.dirPath = self.testDir + "nonEmptyDirectory1/"
      childDirPath = self.dirPath + "childDirectory-1/"
      fileMgr.MakeDirectory(virtualMachine, guestAuth, childDirPath, True)

   def runTest(self):
      recursive = False
      with self.assertRaises(Vim.Fault.DirectoryNotEmpty):
         fileMgr.DeleteDirectory(virtualMachine, guestAuth, self.dirPath, recursive)

class DeleteDirectoryRecursive(TestCase):

   def setUp(self):
      super(DeleteDirectoryRecursive, self).setUp()
      self.dirPath = self.testDir + "nonEmptyDirectory1/"
      childDirPath = self.dirPath + "childDirectory-1/"
      fileMgr.MakeDirectory(virtualMachine, guestAuth, childDirPath, True)

   def runTest(self):
      recursive = True
      fileMgr.DeleteDirectory(virtualMachine, guestAuth, self.dirPath, recursive)


class CreateTempFileErrorInvalidPath(TestCase):

   def runTest(self):
      with self.assertRaises(Vim.Fault.FileNotFound):
         fileMgr.CreateTemporaryFile(virtualMachine, guestAuth,
                                     "pre", "suf", "invalidPath")

class CreateTempFileEmptyPath(TestCase):

   def runTest(self):
      fileMgr.CreateTemporaryFile(virtualMachine, guestAuth, "pre", "suf", "")

class CreateTempFileUnsetPath(TestCase):

   def runTest(self):
      fileMgr.CreateTemporaryFile(virtualMachine, guestAuth, "pre", "suf")

class CreateTempFileFullPath(TestCase):

   def runTest(self):
      fileMgr.CreateTemporaryFile(virtualMachine, guestAuth, "pre", "suf", self.testDir)


class CreateTempDirErrorInvalidPath(TestCase):

   def runTest(self):
      with self.assertRaises(Vim.Fault.FileNotFound):
         fileMgr.CreateTemporaryDirectory(virtualMachine, guestAuth,
                                          "pre", "suf", "invalidPath")

class CreateTempDirEmptyPath(TestCase):

   def runTest(self):
      fileMgr.CreateTemporaryDirectory(virtualMachine, guestAuth, "pre", "suf", "")

class CreateTempDirUnsetPath(TestCase):

   def runTest(self):
      fileMgr.CreateTemporaryDirectory(virtualMachine, guestAuth, "pre", "suf")

class CreateTempDirFullPath(TestCase):

   def runTest(self):
      fileMgr.CreateTemporaryDirectory(virtualMachine, guestAuth,
                                       "pre", "suf", self.testDir)


class MoveFileErrorIncompleteDstPath(TestCase):

   def setUp(self):
      super(MoveFileErrorIncompleteDstPath, self).setUp()
      self.src = self.testDir + "file-1.txt"
      self.dst = self.testDir + "dir-1"

      fileMgr.MakeDirectory(virtualMachine, guestAuth, self.dst, True)
      createFile(self.src)

   def runTest(self):
      overwrite = True
      with self.assertRaises(Vim.Fault.FileAlreadyExists):
         fileMgr.MoveFile(virtualMachine, guestAuth, self.src, self.dst, overwrite)

class MoveFileErrorDstAlreadyExists(TestCase):

   def setUp(self):
      super(MoveFileErrorDstAlreadyExists, self).setUp()
      dirPath1 = self.testDir + "dir-1/"
      self.src = self.testDir + "file-1.txt"
      self.dst = dirPath1 + "file-2.txt"

      fileMgr.MakeDirectory(virtualMachine, guestAuth, dirPath1, True)
      createFile(self.src)
      createFile(self.dst)

   def runTest(self):
      overwrite = False
      with self.assertRaises(Vim.Fault.FileAlreadyExists):
         fileMgr.MoveFile(virtualMachine, guestAuth, self.src, self.dst, overwrite)

class MoveFileToDifferentDirectory(TestCase):

   def setUp(self):
      super(MoveFileToDifferentDirectory, self).setUp()
      dirPath1 = self.testDir + "dir-1/"
      self.src = self.testDir + "file-1.txt"
      self.dst = dirPath1 + "file-2.txt"

      fileMgr.MakeDirectory(virtualMachine, guestAuth, dirPath1, True)
      createFile(self.src)

   def runTest(self):
      overwrite = False
      fileMgr.MoveFile(virtualMachine, guestAuth, self.src, self.dst, overwrite)

class MoveFileToSameDirectory(TestCase):

   def setUp(self):
      super(MoveFileToSameDirectory, self).setUp()
      dirPath1 = self.testDir + "dir-1/"
      self.src = dirPath1 + "file-1.txt"
      self.dst = dirPath1 + "file-2.txt"

      fileMgr.MakeDirectory(virtualMachine, guestAuth, dirPath1, True)
      createFile(self.src)

   def runTest(self):
      overwrite = True
      fileMgr.MoveFile(virtualMachine, guestAuth, self.src, self.dst, overwrite)

class MoveFileErrorSrcNotExisting(TestCase):

   def runTest(self):
      src = "nonExistingFile1.txt"
      dst = "nonExistingFile2.txt"
      overwrite = True
      with self.assertRaises(Vim.Fault.FileNotFound):
         fileMgr.MoveFile(virtualMachine, guestAuth, src, dst, overwrite)


class MoveDirErrorSrcNotExisting(TestCase):

   def runTest(self):
      src = "nonExistingDir1"
      dst = "nonExistingDir2"
      with self.assertRaises(Vim.Fault.FileNotFound):
         fileMgr.MoveDirectory(virtualMachine, guestAuth, src, dst)

class MoveDirErrorDstAlreadyExists(TestCase):

   def setUp(self):
      super(MoveDirErrorDstAlreadyExists, self).setUp()
      self.src = self.testDir + "dir-1/"
      self.dst = self.testDir + "dir-2/"

      fileMgr.MakeDirectory(virtualMachine, guestAuth, self.src, True)
      fileMgr.MakeDirectory(virtualMachine, guestAuth, self.dst, True)

   def runTest(self):
      with self.assertRaises(Vim.Fault.FileAlreadyExists):
         fileMgr.MoveDirectory(virtualMachine, guestAuth, self.src, self.dst)

class MoveDirToDifferentDirectory(TestCase):

   def setUp(self):
      super(MoveDirToDifferentDirectory, self).setUp()
      self.src = self.testDir + "dir-1/"
      dirPath2 = self.testDir + "dir-2/"
      self.dst = dirPath2 + "dir-1/"

      fileMgr.MakeDirectory(virtualMachine, guestAuth, self.src, True)
      fileMgr.MakeDirectory(virtualMachine, guestAuth, dirPath2, True)

   def runTest(self):
      fileMgr.MoveDirectory(virtualMachine, guestAuth, self.src, self.dst)


class ChangeFileAttributesAdminAuth(TestCase):

   def setUp(self):
      super(ChangeFileAttributesAdminAuth, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      if guestAdminAuth == "":
         Log("Skipping test (needs -R & -X for guest root user & passwd)")
         return

      fileDate = datetime(2009, 1, 1, 1, 1, 1)
      fileAttributes = fileDef.PosixFileAttributes()
      fileAttributes.accessTime = fileDate
      fileAttributes.modificationTime = fileDate
      fileAttributes.ownerId = 1
      fileAttributes.groupId = 1
      fileAttributes.permissions = 484

      fileMgr.ChangeFileAttributes(virtualMachine, guestAdminAuth,
                                   self.file, fileAttributes)

class ChangeFileAttributesPosix(TestCase):

   def setUp(self):
      super(ChangeFileAttributesPosix, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      fileDate = datetime(2009, 1, 1, 1, 1, 1)
      fileAttributes = fileDef.PosixFileAttributes()
      fileAttributes.accessTime = fileDate
      fileAttributes.modificationTime = fileDate
      fileAttributes.permissions = 484

      fileMgr.ChangeFileAttributes(virtualMachine, guestAuth,
                                   self.file, fileAttributes)

class ChangeFileAttributesWindows(TestCase):

   def setUp(self):
      super(ChangeFileAttributesWindows, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      fileDate = datetime(2009, 1, 1, 1, 1, 1)
      fileAttributes = fileDef.WindowsFileAttributes()
      fileAttributes.hidden = False
      fileAttributes.accessTime = fileDate
      fileAttributes.modificationTime = fileDate

      with self.assertRaises(Vmodl.Fault.InvalidArgument):
         # This api will pass if executed against a windows VM.
         fileMgr.ChangeFileAttributes(virtualMachine, guestAuth,
                                      self.file, fileAttributes)

class ChangeFileAttributesDefault(TestCase):

   def setUp(self):
      super(ChangeFileAttributesDefault, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      fileAttributes = fileDef.FileAttributes()
      fileMgr.ChangeFileAttributes(virtualMachine, guestAuth,
                                   self.file, fileAttributes)

class ChangeFileAttributesPermissions(TestCase):

   def setUp(self):
      super(ChangeFileAttributesPermissions, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      fileAttributes = fileDef.PosixFileAttributes()
      fileAttributes.permissions = 0o777
      fileMgr.ChangeFileAttributes(virtualMachine, guestAuth,
                                   self.file, fileAttributes)

class ListFilesDirectory(unittest.TestCase):

   def runTest(self):
      fileMgr.ListFiles(virtualMachine, guestAuth, "/tmp")

class ListFilesSingleFile(unittest.TestCase):

   def runTest(self):
      fileMgr.ListFiles(virtualMachine, guestAuth, "/bin/ls")

class ListFilesWithPattern(unittest.TestCase):

   def runTest(self):
      fileMgr.ListFiles(virtualMachine, guestAuth, "/tmp", matchPattern=".*.log")

class ListFilesErrorNotExisting(unittest.TestCase):

   def runTest(self):
      with self.assertRaises(Vim.Fault.FileNotFound):
         fileMgr.ListFiles(virtualMachine, guestAuth, "/tmp/ls")


class HTTPError(Exception):
   def __init__(self, code, message):
      super(HTTPError, self).__init__("%s : %s" % (code, message))
      self.code = code
      self.message = message

def upload(url, body):
   Log("Upload to URL: %s" % url)

   urloptions = urlparse(url)
   conn = HTTPSConnection(urloptions.netloc)

   headers = {"Content-Length" : len(body)}
   conn.request("PUT", urloptions.path + "?" + urloptions.query, body, headers)
   res = conn.getresponse()
   if res.status != 200:
      Log("PUT request failed with errorcode : %s" % res.status)
      raise HTTPError(res.status, res.reason)

   return res;

def initiateAndUpload(virtualMachine, guestAuthentication, dstPath,
                      fileAttributes, fileSize, overwrite):
   result = fileMgr.InitiateFileTransferToGuest(virtualMachine,
      guestAuthentication, dstPath, fileAttributes, fileSize, overwrite)
   url = result.replace('*', host1)
   body = generateStringWithSpecifiedSize(fileSize)
   return upload(url, body)

def download(url):
   Log("Download from URL: %s" % url)

   urloptions = urlparse(url)
   conn = HTTPSConnection(urloptions.netloc)

   body = ""
   headers = {}
   conn.request("GET", urloptions.path + "?" + urloptions.query, body, headers)
   res = conn.getresponse()
   if res.status != 200:
      Log("GET request failed with errorcode : %s" % res.status)
      raise HTTPError(res.status, res.reason)

   return res

def initiateAndDownload(virtualMachine, guestAuth, srcFile):
   result = fileMgr.InitiateFileTransferFromGuest(virtualMachine, guestAuth, srcFile)
   url = result.url.replace('*', host1)
   return download(url)


class FileTransferToGuestErrorAlreadyExists(TestCase):

   def setUp(self):
      super(FileTransferToGuestErrorAlreadyExists, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      fileAttributes = fileDef.FileAttributes()
      overwrite = False
      fileSize = 100
      with self.assertRaises(Vim.Fault.FileAlreadyExists):
         result = fileMgr.InitiateFileTransferToGuest(virtualMachine, guestAuth,
            self.file, fileAttributes, fileSize, overwrite)

class FileTransferToGuestErrorNotAFile(TestCase):

   def runTest(self):
      fileAttributes = fileDef.FileAttributes()
      overwrite = True
      fileSize = 100
      with self.assertRaises(Vim.Fault.NotAFile):
         fileMgr.InitiateFileTransferToGuest(virtualMachine, guestAuth,
            self.testDir, fileAttributes, fileSize, overwrite)

class FileTransferToGuestOverwrite(TestCase):

   def setUp(self):
      super(FileTransferToGuestOverwrite, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      fileDate = datetime(2009, 1, 1, 1, 1, 1)
      fileAttributes = fileDef.PosixFileAttributes()
      fileAttributes.accessTime = fileDate
      fileAttributes.modificationTime = fileDate
      fileAttributes.ownerId = 1
      fileAttributes.groupId = 1
      fileAttributes.permissions = 484
      overwrite = True
      fileSize = 100

      fileMgr.InitiateFileTransferToGuest(virtualMachine, guestAuth,
         self.file, fileAttributes, fileSize, overwrite)

class FileTransferToGuestWindowsFileAttr(TestCase):

   def setUp(self):
      super(FileTransferToGuestWindowsFileAttr, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      fileDate = datetime(2009, 1, 1, 1, 1, 1)
      fileAttributes = fileDef.WindowsFileAttributes()
      fileAttributes.createTime = fileDate
      fileAttributes.accessTime = fileDate
      fileAttributes.modificationTime = fileDate
      fileAttributes.hidden = True
      overwrite = True
      fileSize = 100

      with self.assertRaises(Vmodl.Fault.InvalidArgument):
         # This api will pass if executed against a windows VM.
         fileMgr.InitiateFileTransferToGuest(virtualMachine, guestAuth,
            self.file, fileAttributes, fileSize, overwrite)

class FileTransferToGuestDefaultFileAttr(TestCase):

   def setUp(self):
      super(FileTransferToGuestDefaultFileAttr, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      fileAttributes = fileDef.FileAttributes()
      initiateAndUpload(virtualMachine, guestAuth, self.file, fileAttributes,
         fileSize=100, overwrite=True)

class FileTransferToGuestPosixFileAttr(TestCase):

   def setUp(self):
      super(FileTransferToGuestPosixFileAttr, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      fileAttributes = fileDef.PosixFileAttributes()
      fileAttributes.ownerId = 1
      fileAttributes.permissions = 0o444
      initiateAndUpload(virtualMachine, guestAuth, self.file, fileAttributes,
         fileSize=100, overwrite=True)


class FileTransferFromGuestErrorNotAFile(TestCase):

   def runTest(self):
      with self.assertRaises(Vim.Fault.NotAFile):
         fileMgr.InitiateFileTransferFromGuest(virtualMachine, guestAuth, self.testDir)

class FileTransferFromGuestErrorNotExisting(TestCase):

   def runTest(self):
      file = self.testDir + "nonexistingfile.txt"
      with self.assertRaises(Vim.Fault.FileNotFound):
         fileMgr.InitiateFileTransferFromGuest(virtualMachine, guestAuth, file)


class FileTransferFromGuestDownload(TestCase):

   def setUp(self):
      super(FileTransferFromGuestDownload, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      result = fileMgr.InitiateFileTransferFromGuest(
         virtualMachine, guestAuth, self.file)
      url = result.url.replace('*', host1)
      download(url)

      # second download from the same url should fail
      with self.assertRaises(HTTPError) as ctx:
         download(url)
      err = ctx.exception
      self.assertEqual(err.code, 404)

class FileTransferFromGuestDownloadWhileChanging(TestCase):

   def setUp(self):
      super(FileTransferFromGuestDownloadWhileChanging, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      result = fileMgr.InitiateFileTransferFromGuest(
         virtualMachine, guestAuth, self.file)
      url = result.url.replace('*', host1)

      # expand the content of the file
      arg = ">> " + self.file
      startProgramEx(virtualMachine, guestAuth, "/bin/ls", baseDir, arg)
      download(url)

      result = fileMgr.InitiateFileTransferFromGuest(
         virtualMachine, guestAuth, self.file)
      url = result.url.replace('*', host1)

      # truncate the content of the file
      createFile(self.file)
      download(url)

class FileTransferFromGuestDownloadWhileGrowing(TestCase):

   def setUp(self):
      super(FileTransferFromGuestDownloadWhileGrowing, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createEmptyFile(self.file)

   def runTest(self):
      # Simulate PR 1203102
      result = fileMgr.InitiateFileTransferFromGuest(
         virtualMachine, guestAuth, self.file)
      url = result.url.replace('*', host1)

      # file grows in size
      arg = ">> " + self.file
      startProgramEx(virtualMachine, guestAuth, "/bin/ls", baseDir, arg)
      download(url)

class FileTransferFromGuestDownloadWhilePowercycle(TestCase):

   def setUp(self):
      super(FileTransferFromGuestDownloadWhilePowercycle, self).setUp()
      self.file = self.testDir + "file-1.txt"
      createFile(self.file)

   def runTest(self):
      result = fileMgr.InitiateFileTransferFromGuest(
         virtualMachine, guestAuth, self.file)
      url = result.url.replace('*', host1)

      # power off the VM if needed
      powerOffVM(virtualMachine)

      with self.assertRaises(HTTPError) as ctx:
         download(url)
      err = ctx.exception
      self.assertEqual(err.code, 404)

      powerOnVM(virtualMachine)
      waitForTools(virtualMachine)


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

   # get the fileManager object
   global fileMgr
   fileMgr = svcInst.content.guestOperationsManager.fileManager
   global fileDef
   fileDef = Vim.Vm.Guest.FileManager

   global host1
   host1 = options.host

   waitForTools(virtualMachine)

   testSetup()

   suite = unittest.TestSuite()
   suite.addTest(MakeDirectoryErrorAlreadyExists())
   suite.addTest(MakeDirectoryRecursive())
   suite.addTest(MakeDirectoryNonRecursive())
   suite.addTest(MakeDirectoryParentNotExisting())
   suite.addTest(MakeDirectoryErrorNameTooLong())
   suite.addTest(DeleteFileExisting())
   suite.addTest(DeleteFileErrorNonExisting())
   suite.addTest(DeleteFileErrorNonAFile())
   suite.addTest(DeleteDirectoryErrorNotADirectory())
   suite.addTest(DeleteDirectoryErrorNotExisting())
   suite.addTest(DeleteDirectoryNonRecursive())
   suite.addTest(DeleteDirectoryErrorNotEmpty())
   suite.addTest(DeleteDirectoryRecursive())
   suite.addTest(CreateTempFileErrorInvalidPath())
   suite.addTest(CreateTempFileEmptyPath())
   suite.addTest(CreateTempFileUnsetPath())
   suite.addTest(CreateTempFileFullPath())
   suite.addTest(CreateTempDirErrorInvalidPath())
   suite.addTest(CreateTempDirEmptyPath())
   suite.addTest(CreateTempDirUnsetPath())
   suite.addTest(CreateTempDirFullPath())
   suite.addTest(MoveFileErrorIncompleteDstPath())
   suite.addTest(MoveFileErrorDstAlreadyExists())
   suite.addTest(MoveFileToDifferentDirectory())
   suite.addTest(MoveFileToSameDirectory())
   suite.addTest(MoveFileErrorSrcNotExisting())
   suite.addTest(MoveDirErrorSrcNotExisting())
   suite.addTest(MoveDirErrorDstAlreadyExists())
   suite.addTest(MoveDirToDifferentDirectory())
   suite.addTest(ChangeFileAttributesAdminAuth())
   suite.addTest(ChangeFileAttributesPosix())
   suite.addTest(ChangeFileAttributesWindows())
   suite.addTest(ChangeFileAttributesDefault())
   suite.addTest(ChangeFileAttributesPermissions())
   suite.addTest(ListFilesDirectory())
   suite.addTest(ListFilesSingleFile())
   suite.addTest(ListFilesWithPattern())
   suite.addTest(ListFilesErrorNotExisting())
   suite.addTest(FileTransferToGuestErrorAlreadyExists())
   suite.addTest(FileTransferToGuestErrorNotAFile())
   suite.addTest(FileTransferToGuestOverwrite())
   suite.addTest(FileTransferToGuestWindowsFileAttr())
   suite.addTest(FileTransferToGuestDefaultFileAttr())
   suite.addTest(FileTransferToGuestPosixFileAttr())
   suite.addTest(FileTransferFromGuestErrorNotAFile())
   suite.addTest(FileTransferFromGuestErrorNotExisting())
   suite.addTest(FileTransferFromGuestDownload())
   suite.addTest(FileTransferFromGuestDownloadWhileChanging())
   suite.addTest(FileTransferFromGuestDownloadWhileGrowing())
   suite.addTest(FileTransferFromGuestDownloadWhilePowercycle())

   unittest.TextTestRunner(verbosity=3).run(suite)

# Start program
if __name__ == "__main__":
   main()
