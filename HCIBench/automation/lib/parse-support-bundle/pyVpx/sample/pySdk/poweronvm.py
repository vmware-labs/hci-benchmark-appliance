#!/usr/bin/python
#
# **********************************************************
# Copyright 2010 VMware, Inc.  All rights reserved.
# **********************************************************
"""
Python program for powering on vms on a host on which hostd is running
"""

from optparse import OptionParser, make_option
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim, vmodl
import sys
import atexit


def GetOptions():
    """
   Supports the command-line arguments listed below.
   """

    _CMD_OPTIONS_LIST = [
        make_option("-h", "--host", help="remote host to connect to"),
        make_option("-o", "--port", default=443, help="Port"),
        make_option("-u",
                    "--user",
                    default="root",
                    help="User name to use when connecting to host"),
        make_option("-p",
                    "--password",
                    help="Password to use when connecting to host"),
        make_option("-v",
                    "--vmname",
                    default=[],
                    action="append",
                    help="Name of the Virtual Machine to power on"),
        make_option("-?", "--help", action="store_true", help="Help"),
    ]
    _STR_USAGE = "%prog [options]"

    parser = OptionParser(option_list=_CMD_OPTIONS_LIST,
                          usage=_STR_USAGE,
                          add_help_option=False)
    (options, _) = parser.parse_args()
    return options


def WaitForTasks(tasks, si):
    """
   Given the service instance si and tasks, it returns after all the
   tasks are complete
   """

    pc = si.content.propertyCollector

    taskList = [str(task) for task in tasks]

    # Create filter
    objSpecs = [
        vmodl.query.PropertyCollector.ObjectSpec(obj=task) for task in tasks
    ]
    propSpec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task,
                                                          pathSet=[],
                                                          all=True)
    filterSpec = vmodl.query.PropertyCollector.FilterSpec()
    filterSpec.objectSet = objSpecs
    filterSpec.propSet = [propSpec]
    filter = pc.CreateFilter(filterSpec, True)

    try:
        version, state = None, None

        # Loop looking for updates till the state moves to a completed state.
        while len(taskList):
            update = pc.WaitForUpdates(version)
            for filterSet in update.filterSet:
                for objSet in filterSet.objectSet:
                    task = objSet.obj
                    for change in objSet.changeSet:
                        if change.name == 'info':
                            state = change.val.state
                        elif change.name == 'info.state':
                            state = change.val
                        else:
                            continue

                        if not str(task) in taskList:
                            continue

                        if state == vim.TaskInfo.State.success:
                            # Remove task from taskList
                            taskList.remove(str(task))
                        elif state == vim.TaskInfo.State.error:
                            raise task.info.error
            # Move to next version
            version = update.version
    finally:
        if filter:
            filter.Destroy()


# Start program
def main():
    """
   Simple command-line program for powering on virtual machines on a system.
   """

    options = GetOptions()
    try:
        vmnames = options.vmname
        if not len(vmnames):
            print "No virtual machine specified for poweron"
            sys.exit()

        si = SmartConnect(host=options.host,
                          user=options.user,
                          pwd=options.password,
                          port=int(options.port))
        if not si:
            print "Cannot connect to Host"
            sys.exit()

        atexit.register(Disconnect, si)

        # Retreive the list of Virtual Machines from the invetory objects
        # under the rootFolder
        content = si.content
        objView = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True)
        vmList = objView.view
        objView.Destroy()

        # Find the vm and power it on
        tasks = [vm.PowerOn() for vm in vmList if vm.name in vmnames]

        # Wait for power on to complete
        WaitForTasks(tasks, si)

        print "Virtual Machine(s) have been powered on successfully"
    except vmodl.MethodFault, e:
        print "Caught vmodl fault : " + e.msg
    except Exception, e:
        print "Caught Exception : " + str(e)


# Start program
if __name__ == "__main__":
    main()
