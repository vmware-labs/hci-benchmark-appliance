#!/usr/bin/python

# **********************************************************
# Copyright 2006-2017 VMware, Inc.  All rights reserved. -- VMware Confidential
# **********************************************************

import getopt
import os
import sys
from pyVmomi import types, Vmodl, Vim, SoapStubAdapter
from pyVmomi.SoapAdapter import Serialize
import pyVim.vimApiTypeMatrix
import pyVim.vimApiGraph
from pyVim.connect import SmartConnect, Disconnect
import atexit
from functools import reduce

# The maximum size object to print directly to the terminal if -o -
_MAX_TO_TERM = 1024 * 10  # 10K


def GetPropertyCollector(si):
    content = si.RetrieveContent()
    pc = content.propertyCollector
    return pc


# [(moType, all), (moType, all), ...]
def MakePropertySpecs(managedObjectSpecs):
    propertySpecs = []

    for managedObjectSpec in managedObjectSpecs:
        moType = managedObjectSpec[0]
        all = managedObjectSpec[1]

        propertySpec = Vmodl.Query.PropertyCollector.PropertySpec()
        propertySpec.type = reduce(getattr, moType.split('.'), types)
        propertySpec.all = all

        propertySpecs.append(propertySpec)

    return propertySpecs


def usage():
    print("Usage: vimdump <options> -o file\n")
    print("Options:")
    print("  -h            help")
    print("  -o            output file")
    print("  -U <user>     user to connect as. default is logged in user.")
    print(
        "  -f            only show property collector filter.  Don't execute.")
    print("  -x            produce xml rather than human friendly output")


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hU:fxo:", [
            "help",
            "user=",
            "filteronly",
            "xml",
            "output",
        ])
    except getopt.GetoptError:
        # print help information and exit:
        usage()
        sys.exit(1)

    connectParams = {}
    filteronly = False
    outputFile = None
    xml = False

    for o, a in opts:
        if o in ("-U", "--user"):
            connectParams["user"] = a
        if o in ("-f", "--filteronly"):
            filteronly = True
        if o in ("-x", "--xml"):
            xml = True
        if o in ("-o", "--output"):
            outputFile = a
            if os.path.exists(a):
                print("output file already exists")
                sys.exit(1)
        if o in ("-h", "--help"):
            usage()
            sys.exit()
    if outputFile is None:
        print("Must specify output file\n")
        usage()
        sys.exit(1)

    if outputFile == "-":
        output = sys.stdout
    else:
        output = open(outputFile, "w")

    objectSpec = Vmodl.Query.PropertyCollector.ObjectSpec()
    siInfo = Vim.ServiceInstance("ServiceInstance", None)
    objectSpec.obj = siInfo
    objectSpec.skip = False
    objectSpec.selectSet = pyVim.vimApiGraph.BuildMoGraphSelectionSpec()

    fetchProp = False

    # Build up a property spec that consists of all managed object types
    matrix = pyVim.vimApiTypeMatrix.CreateMoTypeMatrix()
    classNames = matrix.GetClassNames()
    propertySpecs = [[x, fetchProp] for x in classNames]
    propertySpecs = MakePropertySpecs(propertySpecs)

    objectSpecs = [objectSpec]

    filterSpec = Vmodl.Query.PropertyCollector.FilterSpec()
    filterSpec.propSet = propertySpecs
    filterSpec.objectSet = objectSpecs

    filterSpecs = Vmodl.Query.PropertyCollector.FilterSpec.Array([filterSpec])

    if filteronly:
        result = Serialize(filterSpecs)
        header = (
            "<!-- Property collector spec used by vimdump to gather references to -->",
            "<!-- all known managed objects on the system (SOAP serialization).  -->",
            "<!-- Usage: vim-cmd vimsvc/property_dump vimdump-spec.xml -->")
        output.write('\n'.join(header))
        output.write(result)
        return 0

    # Connect
    si = None
    try:
        si = SmartConnect(**connectParams)
    except Exception as e:
        print(e)
        sys.exit(2)
    atexit.register(Disconnect, si)

    pc = GetPropertyCollector(si)
    objectContents = pc.RetrieveContents(filterSpecs)
    objectContents.sort(key=lambda x: x.obj._GetMoId())
    objectContents.sort(key=lambda x: x.obj.__class__.__name__)

    #print objectContents

    output.write("\nFound " + str(len(objectContents)) + " managed objects:")
    i = 1
    for objectContent in objectContents:
        obj = objectContent.obj
        output.write(
            str(i) + ". " + obj.__class__.__name__ + "::" + obj._GetMoId())
        i = i + 1

    output.write("\n")

    mos = [x.obj for x in objectContents]

    i = 1
    for mo in mos:
        objectSpec = Vmodl.Query.PropertyCollector.ObjectSpec()
        objectSpec.obj = mo
        objectSpec.skip = False
        objectSpec.selectSet = []

        propertySpec = Vmodl.Query.PropertyCollector.PropertySpec()
        propertySpec.type = mo.__class__
        propertySpec.all = True

        filterSpec = Vmodl.Query.PropertyCollector.FilterSpec()
        filterSpec.propSet = [propertySpec]
        filterSpec.objectSet = [objectSpec]

        output.write("=============== " + str(i) + ". " +
                     mo.__class__.__name__ + "::" + mo._GetMoId() +
                     " ===============\n")

        objectContents = None
        try:
            objectContents = pc.RetrieveContents([filterSpec])
        except Exception as e:
            output.write("Failed to retrieve contents: %s" % e)

        if objectContents is not None:
            try:
                if xml:
                    toWrite = str(Serialize(objectContents))
                else:
                    toWrite = str(objectContents)
                if len(toWrite) > _MAX_TO_TERM and output.isatty():
                    print(
                        "Output is too large for terminal, please output to ")
                    print("a file using -o <filename>")
                    sys.exit(1)
                output.write(toWrite)
            except Exception as e:
                output.write("Failed to format object: %s" % e)

        output.write("\n")
        i = i + 1

    output.close()


# Start program
if __name__ == "__main__":
    main()
