#!/usr/bin/env python
"""Drop read/write cache for VSAN. 6.2/6.5 tested"""

import optparse
import time
import logging
from logging.handlers import WatchedFileHandler

_logger = logging.getLogger()

import vmware.vsi as vsi

_INTERVAL = 10  # Check every x seconds
_DATA_THRESH = 1024 * 1024 * 100  # Exit if data is below this
_RATE_THRESH = 1024 * 1024  # Exit if drain rate is below this
_LOG_FILE = "/tmp/dropcache.log"

def parseArgs():
    """parse arguments

   @return: options
   """
    opt = optparse.OptionParser()
    opt.add_option(
        "--maxWait",
        "-W",
        type="int",
        action="store",
        default=0,
        help="max wait in seconds. 0=> forever",
    )
    opt.add_option(
        "--noWait", action="store_true", default=False, help="do not wait"
    )
    opt.add_option(
        "--rd",
        "-r",
        action="store_true",
        default=False,
        help="drop read cache",
    )
    opt.add_option(
        "--wr",
        "-w",
        action="store_true",
        default=False,
        help="drop write cache",
    )
    opt.add_option(
        "--verbose",
        action="store_true",
        default=False,
        help="more verbose output",
    )

    options, _ = opt.parse_args()

    if options.verbose:
        logLevel = logging.DEBUG
    else:
        logLevel = logging.WARN

    _logger.setLevel(logLevel)
    handler = WatchedFileHandler(_LOG_FILE)
    handler.setLevel(logLevel)
    logFmt = "%(asctime)s - %(message)s"
    handler.setFormatter(logging.Formatter(logFmt))
    _logger.addHandler(handler)

    if not options.rd and not options.wr:
        _logger.error("Must provide one or more of --rd/--wr")
        exit(1)

    return options


def dropRead():
    """Drop read cache

   """
    _logger.debug("Dropping read cache")
    try:
        disks = vsi.list("/vmkModules/lsom/disks/")
        components = None
    except ValueError:
        _logger.warning("Using old lsom nodes")
        node = "/vmkModules/vsan/lsom/components/"
        components = [node + c for c in vsi.list(node)]

    if components is None:
        components = []
        for disk in disks:
            node = "/vmkModules/lsom/disks/%s/components/" % disk
            try:
                components.extend([node + c for c in vsi.list(node)])
            except:
                _logger.warning("No components in %s", disk)

    if len(components):
        _logger.warning(
            "Clearing out read-cache for %d components", len(components)
        )
        for comp in components:
            vsi.set(comp + "/dropRcCache", 1)
        time.sleep(10)


def dropWrite(wait=None):
    """Drop write cache

   wait: wait for dropCache to complete
              None => return immediately, DO NOT reset nodes
              0    => wait till drop is complete. RESET nodes
              other =>

   """
    _logger.debug("Dropping write cache")
    oldThresh = vsi.get("/vmkModules/plog/plogLogThreshold")
    defRunElev = vsi.get("/config/LSOM/intOpts/plogRunElevator")["cur"]
    oldSleep = vsi.get("/config/LSOM/intOpts/plogElevSleepTime")["cur"]
    if oldThresh < 1000:
        _logger.error(
            "Skipping write cache as log thresh is very small %d", oldThresh
        )
        return

    _logger.warning(
        "Reset using the following commands after drop cache completes"
    )
    _logger.warning(
        "vsish -e set /config/LSOM/intOpts/plogRunElevator %d", defRunElev
    )
    _logger.warning(
        "vsish -e set /config/LSOM/intOpts/plogElevSleepTime %d", oldSleep
    )
    defDdpThrottle = None
    try:
        defDdpThrottle = vsi.get("/config/LSOM/intOpts/dedupElevThrottle")[
            "cur"
        ]
        _logger.warning(
            "vsish -e set /config/LSOM/intOpts/dedupElevThrottle %d",
            defDdpThrottle,
        )
        vsi.set("/config/LSOM/intOpts/dedupElevThrottle", 0)
    except:
        _logger.warning(
            "vsi /config/LSOM/intOpts/dedupElevThrottle does not exist for this build"
        )
        pass

    vsi.set("/config/LSOM/intOpts/plogRunElevator", 1)
    vsi.set("/config/LSOM/intOpts/plogElevSleepTime", 1)

    if wait is None:
        _logger.warning("Returning without resetting vsi nodes")
        return

    start = time.time()
    end = 0
    if wait > 0:
        end = start + wait
    try:
        ssds = buildList()
        while True:
            attempts = 0
            while attempts < 10:
                try:
                    done = checkDrainState(ssds)
                    break
                except:
                    attempts = attempts + 1
                    _logger.warning("dropcache increase for %r times" % attempts)
                    time.sleep(60)
            if done:
                _logger.warning("Drop cache completed")
                break
            if end and time.time() > end:
                _logger.warning(
                    "Drop cache timed out (%d s). Resetting nodes", wait
                )
                break
            time.sleep(_INTERVAL)
    finally:
        _logger.warning(
            "dropWrite returning in %d s, Resetting vsi nodes",
            time.time() - start,
        )
        vsi.set("/config/LSOM/intOpts/plogRunElevator", defRunElev)
        vsi.set("/config/LSOM/intOpts/plogElevSleepTime", oldSleep)
        try:
            vsi.set("/config/LSOM/intOpts/dedupElevThrottle", defDdpThrottle)
        except:
            _logger.warning(
                "vsi /config/LSOM/intOpts/dedupElevThrottle does not exist for this build"
            )
            pass


def buildList():
    """Build list of ssds

   """
    ssds = {}
    node = "/vmkModules/plog/devices/"
    for disk in vsi.list(node):
        isSSD = vsi.get(node + disk + "/info")["isSSD"]
        if isSSD:
            elevNode = node + disk + "/elevStats"
            ssds[disk] = {
                "state": "QUERY",
                "stateval": 0,
                "prevval": vsi.get(elevNode)["plogDataUsage"],
                "node": elevNode,
            }
    return ssds


def checkDrainState(ssds):
    """Update list of ssds

   """
    done = True
    for (diskName, diskInfo) in list(ssds.items()):
        _logger.info(
            diskInfo
            )
        if diskInfo["state"] == "QUERY":
            done = False
            fullData = vsi.get(diskInfo["node"])
            newVal = fullData["plogDataUsage"]
            prevVal = diskInfo["prevval"]
            _logger.info(
                "Prev Value: %d, New Value: %d",
                newVal,
                prevVal
                )
            rate = prevVal - newVal
            if rate >= 0:
                rate /= _INTERVAL
                _logger.info(
                    "Disk %s plog data drain rate %d MB",
                    diskName,
                    rate / (1024 * 1024),
                )
            elif newVal >= 10000000000000000000:
                pass
            else:
                _logger.error(
                    "Disk %s plog data increasing %d MB to %d MB",
                    diskName,
                    prevVal >> 20,
                    newVal >> 20,
                )
                if rate <= -10 * 1024 * 1024:  # Too much new data. raise
                    raise Exception("Disk %s plog data increasing" % diskName)
            _logger.debug(
                "Disk %s waiting. Usage %d MB, DrainRate %d MB",
                diskName,
                newVal / (1024 * 1024),
                rate / (1024 * 1024),
            )
            diskInfo["prevval"] = newVal
            if newVal <= _DATA_THRESH or newVal >= 10000000000000000000: # or rate <= _RATE_THRESH:
                diskInfo["state"] = "WAIT"
                diskInfo["stateval"] = 30  # 30 seconds in wait state
                _logger.debug("Disk %s drain end condition met", diskName)
            continue

        if diskInfo["state"] == "WAIT":
            diskInfo["stateval"] -= _INTERVAL
            if diskInfo["stateval"] <= 0:
                diskInfo["state"] = "DONE"
            else:
                done = False

    return done


if __name__ == "__main__":
    opts = parseArgs()
    if opts.rd:
        dropRead()
    if opts.wr:
        if opts.maxWait:
            maxWait = None
        else:
            maxWait = opts.maxWait
        dropWrite(maxWait)
