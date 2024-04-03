#!/usr/bin/python
"""
Python program for doing host dvs ops

Requirements:
 * pyVmomi, pyVim
 * Needs to be invoked with py.sh rather than regular python executable
 * The target host needs to be running hostd
"""

import sys
from pyVim.connect import Connect
from optparse import OptionParser
from pyVmomi import Vim
from pyVim.configSerialize import SerializeToConfig


def get_options():
    """
    Supports the command-line arguments listed below
    """

    parser = OptionParser()
    parser.add_option("-H",
                      "--host",
                      default="localhost",
                      help="remote host to connect to")
    parser.add_option("-u",
                      "--user",
                      default="root",
                      help="User name to use when connecting to hostd")
    parser.add_option("-p",
                      "--password",
                      default="",
                      help="Password to use when connecting to hostd")
    parser.add_option("-i", "--uuid", help="DVSwitch id")
    parser.add_option("-n", "--name", default="", help="DVSwitch name")
    parser.add_option("--numPorts",
                      type="int",
                      default="64",
                      help="Number of ports on the DVSwitch")
    parser.add_option("-o",
                      "--operation",
                      type="choice",
                      choices=('create', 'delete', 'list', 'print', 'delPorts',
                               'updatePorts', 'updateNics', 'printPortData'),
                      help="Operation to perform")
    parser.add_option("--pnicBacking",
                      type="string",
                      default="",
                      help="string of the form (nicName:portId:connectionId),")
    parser.add_option("-P",
                      "--portList",
                      type="string",
                      default="",
                      help="List of ports")
    parser.add_option("--portSpec",
                      type="string",
                      default="",
                      help="List of ports of form (portId:name:cnxId),")

    (options, _) = parser.parse_args()

    if options.operation != "list" and options.uuid == None:
        parser.error("uuid needs to be specified")

    if options.operation == None:
        parser.error("operation needs to be specified")

    return options


def GetPnicBacking(uplinkList):

    if uplinkList == "":
        return Vim.Dvs.HostMember.PnicBacking()

    uplinks = uplinkList.split(',')
    pnics = []

    for uplinkSpec in uplinks:
        (nic, port, cid) = uplinkSpec.split(":")
        print nic, port, cid
        pnics.append(
            Vim.Dvs.HostMember.PnicSpec(pnicDevice=nic,
                                        uplinkPortKey=port,
                                        connectionCookie=int(cid)))
    return Vim.Dvs.HostMember.PnicBacking(pnicSpec=pnics)


def main():
    """
    Simple command-line program for doing DVS operations on a host.
    """

    options = get_options()

    si = Connect(host=options.host,
                 user=options.user,
                 namespace="vim25/5.5",
                 pwd=options.password)

    dvsManager = si.RetrieveInternalContent(
    ).hostDistributedVirtualSwitchManager

    if options.operation == "list":
        print dvsManager.distributedVirtualSwitch
    elif options.operation == "print":
        dvsConfig = dvsManager.RetrieveDvsConfigSpec(options.uuid)
        print "" + str(dvsConfig)
    elif options.operation == "create":
        if options.name == "":
            print "switch name needed for DVS creation"
            exit(1)

        prodSpec = Vim.Dvs.ProductSpec(vendor="VMware")
        port1 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
            portKey="1000", name="1000", connectionCookie=5)
        port2 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
            portKey="1001", name="1001", connectionCookie=2)
        port3 = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
            portKey="1009", name="1009", connectionCookie=12)

        nicBacking = GetPnicBacking(options.pnicBacking)
        createSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSCreateSpec(
            uuid=options.uuid,
            name=options.name,
            backing=nicBacking,
            productSpec=prodSpec,
            maxProxySwitchPorts=options.numPorts,
            port=[
                port1,
                port2,
                port3,
            ],
            uplinkPortKey=["1000", "1001"],
            modifyVendorSpecificDvsConfig=False,
            modifyVendorSpecificHostMemberConfig=False)
        #        print SerializeToConfig(createSpec)
        dvsManager.CreateDistributedVirtualSwitch(createSpec)
    elif options.operation == "delete":
        dvsManager.RemoveDistributedVirtualSwitch(options.uuid)
    elif options.operation == "updatePorts":
        if options.portSpec == "":
            print "portSpec needed for DVPort updates"
            exit(1)

        portList = options.portSpec.split(',')
        portDataList = []
        for port in portList:
            (pk, name, cid) = port.split(':')
            portData = Vim.Dvs.HostDistributedVirtualSwitchManager.PortData(
                portKey=pk, name=name, connectionCookie=int(cid))
            portDataList.append(portData)

        dvsManager.UpdatePorts(options.uuid, portDataList)

    elif options.operation == "delPorts":
        if options.portList == "":
            print "Port list needed for DVPort deletion"
            exit(1)

        portList = options.portList.split(',')
        dvsManager.DeletePorts(options.uuid, portList)
    elif options.operation == "updateNics":
        nicBacking = GetPnicBacking(options.pnicBacking)

        configSpec = Vim.Dvs.HostDistributedVirtualSwitchManager.DVSConfigSpec(
            uuid=options.uuid, backing=nicBacking)

        #print configSpec
        dvsManager.ReconfigureDistributedVirtualSwitch(configSpec)
    elif options.operation == "printPortData":
        if (options.portList == ""):
            portList = None
        else:
            portList = options.portList.split(',')
        print dvsManager.FetchPortState(options.uuid, portList)
    print("DONE.")


# Start program
if __name__ == "__main__":
    main()
