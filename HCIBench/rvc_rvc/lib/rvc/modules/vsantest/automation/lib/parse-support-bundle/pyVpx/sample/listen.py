#!/usr/bin/python

# **********************************************************
# Copyright 2006 VMware, Inc.  All rights reserved. -- VMware Confidential
# **********************************************************

import getopt
import os
import sys
from pyVmomi import types, Vmodl, Vim, SoapStubAdapter
from pyVmomi.SoapAdapter import Serialize
import pyVim.vimApiTypeMatrix
import pyVim.vimApiGraph
from pyVim.connect import Connect, Disconnect
import atexit


def GetPropertyCollector(si):
    content = si.RetrieveContent()
    pc = content.GetPropertyCollector()
    return pc


def SortByManagedObject(x, y):
    x = x.GetObj()
    y = y.GetObj()
    result = cmp(x.__class__.__name__, y.__class__.__name__)
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
        propertySpec.SetType(reduce(getattr, moType.split('.'), types))
        propertySpec.SetAll(all)

        propertySpecs.append(propertySpec)

    return propertySpecs


def usage():
    print "Usage: vimdump <options>\n"
    print "Options:"
    print "  -h            help"
    print "  -H <host>     host to connect. default is 'localhost'"
    print "  -O <port>     port to connect. default is 443 for SOAP adapter."
    print "  -U <user>     user to connect as. default is logged in user."
    print "  -P <password> password to login."
    print "  -N            Number of changes to listen. Default 9."


def main():
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], "hH:O:U:P:A:N",
            ["help", "host=", "port=", "user=", "password=", "changes="])
    except getopt.GetoptError:
        # print help information and exit:
        usage()
        sys.exit(1)

    host = "localhost"
    port = 443
    user = "root"
    pwd = "ca$hc0w"
    numChanges = 9

    for o, a in opts:
        if o in ("-H", "--host"):
            host = a
        if o in ("-O", "--port"):
            port = int(a)
        if o in ("-U", "--user"):
            user = a
        if o in ("-P", "--password"):
            pwd = a
        if o in ("-N", "--changes"):
            numChanges = int(a)
        if o in ("-h", "--help"):
            usage()
            sys.exit()

    if numChanges < 1:
        numChanges = 1

    objectSpec = Vmodl.Query.PropertyCollector.ObjectSpec()
    siInfo = Vim.ServiceInstance("ServiceInstance", None)
    objectSpec.SetObj(siInfo)
    objectSpec.SetSkip(False)
    objectSpec.SetSelectSet(pyVim.vimApiGraph.BuildMoGraphSelectionSpec())

    fetchProp = True

    # Build up a property spec that consists of all managed object types
    matrix = pyVim.vimApiTypeMatrix.CreateMoTypeMatrix()
    classNames = matrix.GetClassNames()
    propertySpecs = map(lambda x: [x, fetchProp], classNames)
    propertySpecs = MakePropertySpecs(propertySpecs)

    objectSpecs = [objectSpec]

    filterSpec = Vmodl.Query.PropertyCollector.FilterSpec()
    filterSpec.SetPropSet(propertySpecs)
    filterSpec.SetObjectSet(objectSpecs)

    filterSpecs = Vmodl.Query.PropertyCollector.FilterSpec.Array([filterSpec])

    # Connect
    si = None
    try:
        si = Connect(host=host, port=port, user=user, pwd=pwd)
        atexit.register(Disconnect, si)
    except Exception, e:
        print e
        sys.exit(2)

    pc = GetPropertyCollector(si)
    objectContents = pc.RetrieveContents(filterSpecs)
    objectContents.sort(lambda x, y: SortByManagedObject(x, y))

    #   print objectContents

    print "\nFound " + str(len(objectContents)) + " managed objects:"
    i = 1
    for objectContent in objectContents:
        obj = objectContent.GetObj()
        # print str(i) + ". " + obj.__class__.__name__ + "::" + obj._GetMoId()
        i = i + 1
    print ""

    # Create the filter
    filter = pc.CreateFilter(filterSpec, True)

    updateset = pc.WaitForUpdates(None)

    print "Waiting for " + str(numChanges) + " changes:"

    # Loop until we get the desired number of updates
    for i in range(1, numChanges):
        updateset = pc.WaitForUpdates(updateset.GetVersion())
        try:
            print "Change number " + str(i)
            print updateset
        except Exception:
            print "Failed to format updateset object."
            return

    filter.Destroy()


# Start program
if __name__ == "__main__":
    main()
