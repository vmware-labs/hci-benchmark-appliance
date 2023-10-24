import re
import traceback
from pyVmomi import Vim
from pyVmomi import VmomiSupport
import pyVim.invt


class FilePathError(Exception):
    def __init__(self, text):
        self.errorText = text

    def __str__(self):
        return self.errorText


# Bogus datastore used for unit tests of path conversions
unitTestDsName = 'storage1'
unitTestDsPath = '/vmfs/volumes/%s' % unitTestDsName
unitTestDsUuid = '/vmfs/volumes/cafebabe-cafed00d'
unitTestDsSummary = Vim.Datastore.Summary(name=unitTestDsName,
                                          url=unitTestDsUuid,
                                          accessible=True)
unitTestDsInfo = Vim.Vm.DatastoreInfo(datastore=unitTestDsSummary)


def GetDatastoreList(unitTest=False):
    if unitTest:
        return [unitTestDsInfo]
    else:
        envBrowser = pyVim.invt.GetEnv()
        cfgTarget = envBrowser.QueryConfigTarget(None)
        return cfgTarget.GetDatastore()


def FsPathToTuple(path, unitTest=False):
    """
    Transforms fs-like filename to inventory filename tuple

    e.g. '/vmfs/volumes/Storage1/foo/bar.vmx' -> ('Storage1','foo/bar.vmx')
    e.g. '/vmfs/volumes/some-volume-uuid/a.vmx' -> ('Storage1','a.vmx')
    e.g. '/vmfs/volumes/Storage1' -> ('Storage1','')
    """
    try:
        m = re.match('(/vmfs/volumes/([^/]+))/?(.*)', path)
        dsList = GetDatastoreList(unitTest)
        for ds in dsList:
            datastore = ds.GetDatastore()
            if datastore.GetAccessible():
                dsname = datastore.GetName()
                url = datastore.GetUrl()
                (myUrl, myDsname, myFile) = m.groups()
                if dsname == myDsname:
                    print('INFO: Found datastore by name [%s] -> %s' %
                          (dsname, url))
                    return (dsname, myFile)
                if url == myUrl:
                    print('INFO: Found datastore by url [%s] -> %s' %
                          (dsname, url))
                    return (dsname, myFile)
        raise FilePathError('no datastore found for path "%s"' % path)
    except:
        traceback.print_exc()
        raise FilePathError('path "%s" not valid' % path)


def FsPathToDsPath(path):
    """
    Transforms fs-like filename to inventory filename

    e.g. '/vmfs/volumes/Storage1/foo/bar.vmx' -> '[Storage1] foo/bar.vmx'
    e.g. '/vmfs/volumes/some-fancy-volume-uuid/a.vmx' -> '[Storage1] a.vmx'
    """
    try:
        (dsname, relative) = FsPathToTuple(path)
        return '[%s] %s' % (dsname, relative)
    except:
        raise FilePathError('path "%s" not valid' % path)


def DsPathToFsPath(path):
    """
    Transforms inventory filename to fs-like filename

    e.g. '[Storage1] a.vmx' -> '/vmfs/volumes/Storage1/a.vmx'
    """
    try:
        m = re.match(r'\[([^\]]+)\] (.*)', path)
        return '/vmfs/volumes/%s/%s' % tuple(m.groups())
    except:
        raise FilePathError('path "%s" not valid' % path)


def DsPathToDsName(path):
    """
    Transforms inventory filename to datastore name

    e.g. '[Storage1] a.vmx' -> 'Storage1'
    """
    try:
        m = re.match(r'\[([^\]]+)\] .*', path)
        return m.groups()[0]
    except:
        raise FilePathError('path "%s" not valid' % path)


def TestFsPathToTuple(fsPath, ds, relPath):
    print('TestFsPathToTuple: "%s" -> ("%s", "%s")' % (fsPath, ds, relPath))
    (myDs, myRelPath) = FsPathToTuple(fsPath, unitTest=True)
    if ds != myDs or relPath != myRelPath:
        raise Exception(
            'TestFsPathToTuple: expected ("%s", "%s"), actual ("%s", %s")' %
            (ds, relPath, myDs, myRelPath))


def UnitTest():
    fileName = 'foo/bar.vmx'
    TestFsPathToTuple('%s' % unitTestDsPath, unitTestDsName, '')
    TestFsPathToTuple('%s/' % unitTestDsPath, unitTestDsName, '')
    TestFsPathToTuple('%s/%s' % (unitTestDsPath, fileName), unitTestDsName,
                      fileName)
    TestFsPathToTuple('%s/' % unitTestDsPath, unitTestDsName, '')
    TestFsPathToTuple('%s' % unitTestDsUuid, unitTestDsName, '')
    TestFsPathToTuple('%s/' % unitTestDsUuid, unitTestDsName, '')
    TestFsPathToTuple('%s/%s' % (unitTestDsUuid, fileName), unitTestDsName,
                      fileName)


# Start program
if __name__ == "__main__":
    UnitTest()
