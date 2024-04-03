#!/usr/bin/python
"""
Based on
https://opengrok.eng.vmware.com/source/xref/main.perforce.1666/bora/support/scripts/vmkflames.py

Process vmkstats output to generate intermediate file cpuFlame.fl
This is then consumed by flamegraph.pl to generate cpuFlame.svg

It runs on any ESXi as well as any OS with python.

Syntax:
<PATH>/vmkflames.py -d <vmkstats output dir> -w WORLD [WORLD ...]

Examples:
# python vmkflames.py -d /vmkstatsdir                   OR
# python vmkflames.py -d /vmkstatsdir -w 1234 1324      OR

"""
import argparse
import json
import logging
import os
import re
from collections import defaultdict


logging.basicConfig(level=logging.ERROR)
log = logging.getLogger(__name__)


def readLines(filename):
    try:
        with open(filename) as f:
            return f.readlines()
    except (IOError, OSError):
        return None


def sortDict(d):
    """return copy of given dictionary with values sorted in descending
       order

    @param d: input dictionary
    """
    sd = sorted(d.items(), key=lambda i: i[0], reverse=True)
    return sd


class VmkstatsFlames:
    def __init__(self, vmkstatsDir, vsanworlds):
        """
        Initialize the VmkStats object
        :param vmkstatsDir: vmkstats result directory
        :param vsanworlds: vsanworlds.json file
        """
        self.vmkstatsDir = vmkstatsDir
        self.vsanworlds = json.load(open(vsanworlds))
        # Convert str to int
        for module in self.vsanworlds:
            self.vsanworlds[module] = [int(x) for x in self.vsanworlds[module]]

        self.SAMPLES = "samples"
        self.CALLSTACKS = "callStacks"
        self.SYMBOLTABLE = "symbolTable.k"

        self.samples = ""
        self.callStacks = ""
        self.symbolTable = ""
        self.symCache = {}
        self.symAddrDict = {}
        self.symSizeDict = {}
        self.stackDict = {}
        self.traceCount = defaultdict(dict)
        self.traceAddrs = defaultdict(dict)
        self.idmax = defaultdict(int)

    def loadSymbols(self, symbolTable):
        """
        Load symbols in file symbolTable.k
        Example: 0x420019400710 0x14 VSI_ParamListUsedSize
        For each function, starting address will be in symAddrDict,
        size of function text segment will be in symSizeDict and the
        key for both is the function start address
        """

        p = re.compile(r"0x([\dabcdef]{1,}) 0x([\dabcdef]{1,}) (.*)\n")

        for sym in symbolTable:
            msym = p.match(sym)
            if msym:
                faddr = msym.group(1)
                fsize = msym.group(2)
                fsym = msym.group(3)
                self.symAddrDict[faddr] = fsym
                self.symSizeDict[faddr] = fsize

    def findSymbol(self, addr, sortedSym):
        """
        Finds the symbol that falls within a given function's text segment,
        given an address and populates to symCache for later faster lookups.
        If already available in the cache, it returns the symbol from cache.
        Also caches the fact that address could not be resolved.
        TBD: Opportunity to speed this up by using binary search
        """
        symbol = None
        if self.symCache.get(addr, 0):
            return self.symCache[addr]

        inaddr = int(addr, 16)

        for a, _ in sortedSym:
            faddr = int(a, 16)
            fsize = int(self.symSizeDict[a], 16)
            if inaddr in range(faddr, faddr + fsize):
                self.symCache[addr] = self.symAddrDict[a]
                symbol = self.symAddrDict[a]
                break
        else:
            # Didn't find the address cache
            self.symCache[addr] = "SymNotFound"

        return symbol

    def loadCallstacks(self, callStacks):
        """
        callStacks file format:      3 k:42001975dd15 k:4200194bc3a9 k:420019758c22
        From this file, this function loads stacktraces into a dictionary - stackDict.
        key is the callstackId and value is the entire stack trace for that ID
        """

        p = re.compile(r"(\d{1,}) (.*)")

        for c in callStacks:
            mc = p.match(c)
            if mc:
                callId = mc.group(1)
                stkaddrs = mc.group(2)
                self.stackDict[callId] = stkaddrs

    def putTraceForModule(self, module, traceid, samplecount):
        """
        Function for putting the parsed values from samples file
        and the callstack trace for a specific module into a per
        module data-structure.

        :param module: name of the module
        :param traceid: callstack trace id
        :param samplecount: number of samples for this record
        """
        self.traceCount[module][traceid] = self.traceCount[module].get(
            traceid, 0
        ) + int(samplecount)
        if self.idmax[module] < int(traceid):
            self.idmax[module] = int(traceid)
        try:
            self.traceAddrs[module][traceid] = self.stackDict[traceid]
        except KeyError:
            pass

    def processStats(self):
        """
        Main driver function for this class.
        This function accomplishes the following:

        Reads in the three files samples, callStacks, symbolTable.k and loads the latter two into
        various dictionaries. It then goes over each sample and reconstructs the stacktrace based
        on resolving the addresses in the callstackID to symbols.

        It then creates file cpuFlame.fl which can then be used as input to flamegraph.pl to
        generate a flamegraph in svg format.
        """
        self.samples = readLines(os.path.join(self.vmkstatsDir, self.SAMPLES))
        self.callStacks = readLines(
            os.path.join(self.vmkstatsDir, self.CALLSTACKS)
        )
        self.symbolTable = readLines(
            os.path.join(self.vmkstatsDir, self.SYMBOLTABLE)
        )
        if (
            (not self.samples)
            or (not self.callStacks)
            or (not self.symbolTable)
        ):
            print("samples")
            log.error(
                "One or more of the files: samples, callStacks, symbolTable.k"
                "are not present in specified directory"
            )
            return

        # Load call stack trace addresses and symbol table into local
        # dictionaries

        self.loadSymbols(self.symbolTable)
        sortedSym = sortDict(self.symAddrDict)
        self.loadCallstacks(self.callStacks)

        # Read each sample and resolve to get stacktrace
        # Write stacktrace and count to file cpuFlame.fl

        # regex compile pattern for samples in a plain vmkstats collection of kernel
        # Example: k:42001950c264 907 0 2 9 0 2102771 0

        k = re.compile(
            r"k:([\dabcdef]{1,}) (\d{1,}) (\d{1,}) (\d{1,}) (\d{1,}) (\d{1,}) (\d{1,}) (\d{1,})"
        )

        for sample in self.samples:
            ms = k.match(sample)
            if ms:
                traceid = ms.group(2)
                samplecount = ms.group(4)
                worldid = int(ms.group(7))

                # Adding this record to allWorlds.
                # Will add "allWorlds" as a dummy entry to self.vsanworlds later
                self.putTraceForModule("allWorlds", traceid, samplecount)

                for module in self.vsanworlds:
                    if worldid in self.vsanworlds[module]:
                        break
                else:
                    continue

                self.putTraceForModule(module, traceid, samplecount)

        outputFiles = []
        # Adding dummy entry for allWorlds
        self.vsanworlds["allWorlds"] = []
        for module in self.vsanworlds:
            outputFile = os.path.join(self.vmkstatsDir, module + ".fl")
            outputFiles.append(outputFile)
            with open(outputFile, "w") as fh:
                # We now process the traces that looks like this at this stage:
                # k:420019758c22;k:4200194bc3a9;k:42001975dd15 1
                #
                # The trace is now reversed and is in in kernel addresses
                # Reverse the trace after splitting the addresses at ';' and store it in reverseTrace
                #
                # Remove the k: part of the address and store it in noKTrace
                #
                # Resolve the addresses into symbols and store the trace in resolvedTrace
                #
                for i in range(self.idmax[module]):
                    count = self.traceCount[module].get(str(i), 0)
                    if count == 0:
                        continue

                    try:
                        addrs = self.traceAddrs[module][str(i)]
                        reverseTrace = ";".join(reversed(addrs.split()))
                        if not reverseTrace:
                            continue
                    except KeyError:
                        continue

                    # Remove 'k:' and 'u:userworldID' from the address strings
                    noKTrace = reverseTrace.replace("k:", "")

                    # Resolve to symbol and create the stacktrace list
                    resolvedTrace = [
                        self.findSymbol(i, sortedSym)
                        for i in noKTrace.split(";")
                    ]

                    # Do not use samples with count = 1
                    if len(resolvedTrace) == 1:
                        continue

                    # create stacktrace
                    stackTrace = ";".join(resolvedTrace)
                    fh.write(stackTrace + " " + str(count) + "\n")

        return outputFiles


def main():
    """
    Generating flamegraph from vmkstats
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dir",
        "-d",
        action="store",
        default=None,
        help="vmkstats collection directory",
        required=True,
    )
    parser.add_argument(
        "--vsanworlds",
        "-v",
        action="store",
        default=None,
        help="vsanworlds.json file",
        required=True,
    )

    args = parser.parse_args()
    vmkstats = VmkstatsFlames(args.dir, args.vsanworlds)
    vmkstats.processStats()


if __name__ == "__main__":
    main()
