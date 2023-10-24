#!/usr/bin/python
"""
Python program for doing vswif/vmknic ops

Requirements:
 * pyVmomi, pyVim
 * Needs to be invoked with py.sh rather than regular python executable
 * The target host needs to be running hostd
"""

import sys
import pyVim.host
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
                      default="10.20.104.76",
                      help="remote host to connect to")
    parser.add_option("-u",
                      "--user",
                      default="root",
                      help="User name to use when connecting to hostd")
    parser.add_option("-p",
                      "--password",
                      default="",
                      help="Password to use when connecting to hostd")
    parser.add_option("-d", "--device", help="device id")
    parser.add_option("-P", "--portgroup", default="", help="portgroup name")
    parser.add_option(
        "-t",
        "--type",
        type="choice",
        default="vmk",
        choices=('cos', 'vmk'),
        help="DVPort connection to use dvsId:dvPortId:connectionId")
    parser.add_option(
        "-D",
        "--dvport",
        type="string",
        default="",
        help="DVPort connection to use dvsId:dvPortId:connectionId")
    parser.add_option("-o",
                      "--operation",
                      type="choice",
                      choices=('create', 'delete', 'reconnect', 'list',
                               'listEx'),
                      help="Operation to perform")
    parser.add_option("-i",
                      "--ipAddress",
                      type="string",
                      default="",
                      help="IP address of interface."
                      "For DHCP, specify dhcp."
                      "For static, specify IPAddress:SubnetMask")

    (options, _) = parser.parse_args()

    if options.operation == None:
        parser.error("operation needs to be specified")

    return options


def GetVnics(netSys, type):
    if type == 'vmk':
        return netSys.networkInfo.vnic
    elif type == 'cos':
        return netSys.networkInfo.consoleVnic


def Str2PortConnection(cstr):
    (swid, portid, cnxid) = cstr.split(':')
    swid = swid.strip('\'')
    return Vim.Dvs.PortConnection(switchUuid=swid,
                                  portKey=portid,
                                  connectionCookie=int(cnxid))


def main():
    """
    Simple command-line program for doing DVS operations on a host.
    """

    options = get_options()

    si = Connect(host=options.host,
                 user=options.user,
                 namespace="vim25/5.5",
                 pwd=options.password)

    netSys = pyVim.host.GetHostSystem(si).GetConfigManager().networkSystem

    if options.operation == "list":
        nicList = GetVnics(netSys, options.type)
        for nic in nicList:
            if (nic.GetPortgroup() != ""):
                cnx = nic.GetPortgroup()
            else:
                portCnx = nic.GetSpec().GetDistributedVirtualPort()
                cnx = portCnx.GetSwitchUuid() + ":" + portCnx.GetPortKey()
                cnx += ":" + str(portCnx.GetConnectionCookie())
            print nic.GetDevice(), " : ", cnx

    elif options.operation == "listEx":
        print GetVnics(netSys, options.type)

    elif options.operation == "create":
        portCnx = None
        if options.dvport != "":
            portCnx = Str2PortConnection(options.dvport)

        if options.ipAddress == "dhcp":
            ipConfig = Vim.Host.IpConfig(dhcp=True)
        else:
            (ipAddr, netmask) = options.ipAddress.split(":")
            ipConfig = Vim.Host.IpConfig(dhcp=False,
                                         ipAddress=ipAddr,
                                         subnetMask=netmask)

        spec = Vim.Host.VirtualNic.Specification(
            ip=ipConfig, distributedVirtualPort=portCnx)

        print spec
        if options.type == 'vmk':
            netSys.AddVirtualNic(options.portgroup, spec)
        elif options.type == 'cos':
            netSys.AddServiceConsoleVirtualNic(options.portgroup, spec)

    elif options.operation == "delete":
        if options.device == "":
            print "Need to specify the device"

        if options.type == 'vmk':
            netSys.RemoveVirtualNic(options.device)
        elif options.type == 'cos':
            netSys.RemoveServiceConsoleVirtualNic(options.device)

    elif options.operation == "reconnect":
        if options.device == "":
            print "Need to specify the device"

        portCnx = None
        pgCnx = None
        if options.dvport != "":
            portCnx = Str2PortConnection(options.dvport)
        if options.portgroup != "":
            pgCnx = options.portgroup

        spec = Vim.Host.VirtualNic.Specification(
            distributedVirtualPort=portCnx, portgroup=pgCnx)

        print "Sending spec : ", spec
        if options.type == 'vmk':
            netSys.UpdateVirtualNic(options.device, spec)
        elif options.type == 'cos':
            netSys.UpdateServiceConsoleVirtualNic(options.device, spec)

    print("DONE.")


# Start program
if __name__ == "__main__":
    main()
