#!/usr/bin/python -u

############################################################
# Copyright (C) 2013 VMware, Inc.
# All Rights Reserved
############################################################

#
# groupPowerOn.py --
#
#	A microbenchmark to measure the performance of the datacenter power-on operation.
#       The microbenchmark queries the VC server to get the list of vms available, and
#       performs datacenter power-on operations on those VMs.
#
#       Therefore the virtual machines should be registered with the VC host before
#       invoking this microbenchmark.
#
#       To run the benchmark :
#       > export TESTVPX_PYVPX=$VMTREE/build/vpx/$VMBLD/pyVpx
#       > $TESTVPX_PYVPX/py.sh $VMTREE/vim/py/tests/groupPowerOn.py | tee output.log
#
#       XXX- Todo :
#       Take commandline options instead of hard coding them.
#
from __future__ import print_function

from pyVim.connect import Connect, Disconnect
from pyVim import connect, task, invt, vimutil
from pyVmomi import Vim
import sys, os, getopt, time, atexit, threading, random, optparse
from pyVim.helpers import Log


###############################################################################
#
# RequestThread class--
#
#      The base thread class that performs actions (power-on or power-off) on a
#      set of "numVms" vms starting at index "startIndex". The vms belong to the
#      virtual datacenter "dc".
#
#
###############################################################################


class RequestThread(threading.Thread) :
    def __init__(self, id, dc, vms, startIndex, numVms, batchSize):
        self.id = id
        self.dc = dc
        self.vms = vms
        self.startIndex = startIndex
        self.numVms = numVms
        self.batchSize = batchSize

        self.result = []

        threading.Thread.__init__(self)

    def run(self) :
        # needs to be overridden by a subclass
        assert(False)

###############################################################################
#
# PowerOnRequestThread --
#
#    Thread class implementing VM poweron.
#
###############################################################################

class PowerOnRequestThread(RequestThread) :
    def __init__(self, id, dc, vms, startIndex, numVms,
                 batchSize) :
        RequestThread.__init__(self, id, dc, vms, startIndex, numVms,
                               batchSize)

    def run(self) :
        vmsProcessed = 0
        startIndex = self.startIndex
        while (vmsProcessed < self.numVms) :
            vmsToProcess = self.batchSize
            if (vmsProcessed + vmsToProcess > self.numVms) :
                vmsToProcess = self.numVms - vmsProcessed

            try :
                startTime = int(time.time() * 1000)

                t1 = self.dc.PowerOnVm(self.vms[startIndex :
                                                    startIndex + vmsToProcess])
                task.WaitForTask(t1)
                result = t1.info.result
                tasks = []
                for t in result.attempted:
                    tasks.append(t.task)
                if tasks:
                    task.WaitForTasks(tasks, raiseOnError = False)

                endTime = int(time.time() * 1000)
                print("PowerOn for vms(%d-%d) took %d milliseconds" % (startIndex,
                                                                       startIndex +
                                                                       vmsToProcess - 1,
                                                                       endTime - startTime))
                self.result.append((startIndex, vmsToProcess, endTime - startTime))

            except Exception as e:
                print("PowerOn failed for vms (%d-%d)test due to exception: %s"
                      % (startIndex, startIndex + vmsToProcess - 1, e))
                self.result.append((startIndex, vmsToProcess, -1))

            vmsProcessed += vmsToProcess
            startIndex += vmsToProcess


###############################################################################
#
# PowerOffRequestThread --
#
#  Thread class implementing VM power-off
#
###############################################################################


class PowerOffRequestThread(RequestThread):
    def __init__(self, id, dc, vms, startIndex, numVms,
                 batchSize) :
        RequestThread.__init__(self, id, dc, vms, startIndex, numVms, batchSize)

    def run(self) :
        vmsProcessed = 0
        startIndex = self.startIndex

        while (vmsProcessed < self.numVms) :
            vmsToProcess = self.batchSize
            if (vmsProcessed + vmsToProcess > self.numVms) :
                vmsToProcess = self.numVms - vmsProcessed

            try :
                startTime = int(time.time() * 1000)
                tasks = [vm.PowerOff() for vm in
                         self.vms[startIndex: startIndex + vmsToProcess]]
                task.WaitForTasks(tasks, raiseOnError = False)
                endTime = int(time.time() * 1000)
                print("PowerOff for vms(%d-%d) took %d milliseconds"
                      % (startIndex, startIndex + vmsToProcess - 1,
                         endTime - startTime))
                self.result.append((startIndex, vmsToProcess, endTime - startTime))

            except Exception as e:
                print("PowerOff failed for vms (%d-%d)test due to exception: %s"
                      % (self.startIndex, startIndex + vmsToProcess - 1, e))
                self.result.append((startIndex, vmsToProcess, -1))

            vmsProcessed += vmsToProcess
            startIndex += vmsToProcess

###############################################################################
#
# ThreadFactory --
#
#      A factory of the RequestThread class which determines the number of threads to
#      create, and how to distribute the work among the threads.
#
#
###############################################################################

class ThreadFactory :
    def __init__(self, dc, vms, threadClass, maxThreads, batchSize) :
        self.dc = dc
        self.vms = vms
        self.threadClass = threadClass

        # decide how many threads should be used
        numVms = len(vms)

        if (batchSize > numVms) :
            batchSize = numVms

        if (batchSize <= 0) :
            batchSize = 1

        numThreads = numVms / batchSize

        if (numThreads > maxThreads) :
            numThreads = maxThreads

        self.numThreads = numThreads
        self.batchSize = batchSize

        vmsPerThread = 0
        if (self.numThreads > 0) :
            # decide how many vms to be serviced by 1 thread
            vmsPerThread = len(self.vms) / self.numThreads
            if (len(self.vms) % self.numThreads != 0) :
                vmsPerThread += 1

        self.vmsPerThread = vmsPerThread

        print("numThreads=%d, batchSize=%d, vmsPerThread=%d" % (self.numThreads,
                                                                self.batchSize,
                                                                self.vmsPerThread))

    def doWork(self) :
        threads = []

        # start the threads
        for i in range(0, self.numThreads) :
            startIndex = i * self.vmsPerThread
            endIndex = startIndex + self.vmsPerThread - 1
            if (endIndex >= len(self.vms)) :
                endIndex = len(self.vms) - 1

            numVms = endIndex - startIndex + 1

            print("Starting thread " + str(i) + " of class " + str(self.threadClass) +
                  " to process vms " + str(startIndex) + " to " + str(startIndex + numVms - 1))

            t = self.threadClass(i, self.dc, self.vms, startIndex, numVms,
                                 self.batchSize)

            threads.append(t)

            t.start()

        # wait for the threads to finish.
        overallResult = []
        for t in threads :
            if t.isAlive :
                t.join()
                overallResult += t.result
            else :
                # The operation failed
                overallResult.append((t.startIndex, t.numVms, -1))

        # the succesful completions
        success = [(s,n,t) for (s,n,t) in overallResult if t != -1]
        return (success, overallResult)

###############################################################################
#
# GetVms --
#
#      Return the vms present in the virtual datacenter "dc".
#      The powered-on and powered-off vms are returned separately along with
#      the set of all vms.
#
#
###############################################################################

def GetVms(dc) :
    # XXX : Sometimes vms appear directly as dc.vmFolder.childEntity[], and some other
    # times as dc.vmFolder.childEntity[0].childEntity[]. Maybe an artifact of whether
    # or not RPs are configured in the cluster.
    entities = dc.vmFolder.childEntity[0].childEntity
    print("Found %d entities of type %s" % (len(entities), str(type(entities))))

    vms = entities

    poweredOnVms = []
    poweredOffVms = []

    for vm in vms :
        if vm.runtime.powerState == Vim.VirtualMachine.PowerState.poweredOn :
            poweredOnVms.append(vm)
        elif vm.runtime.powerState == Vim.VirtualMachine.PowerState.poweredOff :
            poweredOffVms.append(vm)

    print("dc=%s total vms=%d, powered on=%d, powered off=%d" % (dc.name, len(vms),
                                                                 len(poweredOnVms),
                                                                 len(poweredOffVms)))
    return(poweredOffVms, poweredOnVms, vms)

if __name__ == "__main__" :
    VC_SERVER = "10.138.119.206"
    VC_PORT = 443
    USER = 'root'
    PASSWD = 'vmware'
    POWERON_THREADS=16
    POWERON_BATCHSIZE=8
    POWERON_BATCHES_PER_THREAD=10

    try:
        si = Connect(host = VC_SERVER, port = VC_PORT, user = USER, pwd = PASSWD)
    except Exception as err:
        print("Login failed: " + str(err))
        sys.exit(-1)
    else :
        print("Connection with %s successful" % VC_SERVER)

    atexit.register(Disconnect, si)
    dc = si.content.rootFolder.childEntity[0]


    # Power off the vms which are powered on.
    (dummy1, poweredOnVms, dummy2) = GetVms(dc)
    powerOffThreadFactory = ThreadFactory(dc, poweredOnVms, PowerOffRequestThread,
                                          10, #maxThreads
                                          10) #batchSize
    (success, result) = powerOffThreadFactory.doWork()

    # Find out all the powered off vms.
    (poweredOffVms, dummy1, dummy2) = GetVms(dc)
    # Select the vms to poweron
    vmsToPowerOn = poweredOffVms[0:POWERON_THREADS*POWERON_BATCHSIZE*POWERON_BATCHES_PER_THREAD]
    powerOnThreadFactory = ThreadFactory(dc, poweredOffVms, PowerOnRequestThread,
                                         POWERON_THREADS, #maxThreads
                                         POWERON_BATCHSIZE)  #batchSize
    (success, result) = powerOnThreadFactory.doWork()


    # Analyze the results.
    print("%d out of %d power-on attempts succesful" % (len(result), len(success)))
    totalTime = 0
    minimum = 0
    maximum = 0
    numBatches = 0
    for (startIndex, numVms, timeTaken) in result :
        if (timeTaken != -1) :
            print("vms(%d:%d) powered on in (%d.%03d) seconds" % (startIndex,
                                                                  startIndex + numVms - 1,
                                                                  timeTaken / 1000,
                                                                  timeTaken % 1000))
            if (minimum == 0 or minimum > timeTaken) :
                minimum = timeTaken
            if (maximum == 0 or maximum < timeTaken) :
                maximum = timeTaken

            totalTime += timeTaken
            numBatches += 1

        else : # power-on failed
            print("vms(%d:%d) could not be powered on" % (startIndex,
                                                          startIndex + numVms - 1))

    if (numBatches == 0) :
        average = 0
    else :
        average = totalTime / numBatches

    print("%d batches of vms powered on with (max=%d, min=%d, average=%d) "
          "millseconds" % (numBatches, maximum, minimum, average))


    # Finally power off all the powered on vms.
    (dummy, poweredOnVms, dummy) = GetVms(dc)
    powerOffThreadFactory = ThreadFactory(dc, poweredOnVms, PowerOffRequestThread,
                                          10,
                                          10)
    powerOffThreadFactory.doWork()
