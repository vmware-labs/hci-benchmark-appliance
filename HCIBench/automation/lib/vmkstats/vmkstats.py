"""VMKstats collector"""
import json
import logging
import optparse
import os
import re
import time
from collections import defaultdict
from logging.handlers import WatchedFileHandler

import vmware.vsi as vsi

Logger = logging.getLogger()

_LOG_FILE = "/tmp/vmkstats.log"

_VMKSTATSDUMPER_CMD = "/usr/lib/vmware/vmkstats/bin/vmkstatsdumper"

_WORLD_REGEX_MAP = {
    # LSOM Worlds
    "LSOMLLOG": r"^VSAN_(.*)_LSOMLLOG$",
    "LSOMHelper": r"LSOMHelper-(.*)",
    "LLOGHelper": r"^LLOGHelper$",
    "PLOG": r"^VSAN_(.*)_PLOG$",
    "PLOGDDP": r"^VSAN_(.*)_PLOGDDP$",
    "PLOGHelperQueue": r"^PLOGHelperQueue$",
    "LFHelper": r"LFHelper",
    # LSOM2 Worlds
    "LSOM2IO": r"LSOM2-IO-(.*)",
    "LSOM2-BG": r"LSOM2-BG-(.*)",
    "splinter_bg_thread": r"splinter(.*)_bg_thread",
    "splinter_memtable_thread": r"splinter(.*)_memtable_thread",
    "splinter_snowplough_thread": r"splinter(.*)_snowplough_thread",
    # DOM Worlds
    "CompServer": r"VSAN_(.*)_CompServer",
    "Client": r"VSAN_(.*)_Client",
    "Owner": r"VSAN_(.*)_Owner",
    # PSA Worlds
    "Cmpl-vmbha": r"Cmpl-vmhba(.*)-(.*)",
    "NVMeComplWorld": r"NVMeComplWorld-(.*)",
    # zDOM Worlds
    "zDOM-common": r"zDOM-com p(.*)",
    "zDOM-cpu": r"zDOM-cpu p(.*)",
    "zDOM-snap-deleter": r"zDOM-snap deleter",
    "zDOM-vtxWB-hot-reg": r"zDOM-vtxWB-hot-reg",
    "zDOM-vtxWB-cold-reg": r"zDOM-vtxWB-cold-reg",
    "zDOM-vtxWB-hot-vat": r"zDOM-vtxWB-hot-vat",
    "zDOM-vtxWB-cold-vat": r"zDOM-vtxWB-cold-vat",
    "zDOM-seg-cleaner": r"zDOM-seg cleaner",
    "zDOM-bank-flusher": r"zDOM-bank-flusher",
    "zDOM-LogIO": r"zDOM-LogIO",
    "zDOM-bank-writer": r"zDOM-bank-writer",
    # RDT Worlds
    "rdtIOWorld": r"rdtIOWorld",
    "RDT_RDMA_Reconfig_Helper": r"RDT RDMA Reconfig Helper",
    "rdtNetworkWorld": r"rdtNetworkWorld",
    "rdtConnectionStateCheckWorld": r"rdtConnectionStateCheckWorld",
    "rdtMemCongestionWorld": r"rdtMemCongestionWorld",
    "rdtMarkPendingAcksWorld": r"rdtMarkPendingAcksWorld",
    "rdtRdmaRetryWorld": r"rdtRdmaRetryWorld",
    "rdtTCPCleanupWorld": r"rdtTCPCleanupWorld",
    # Network Worlds
    "vmnicPollWorld": r"vmnic(.*)pollWorld-(.*)",
}


class Vmkstats(object):
    """VMKstats object"""

    def __init__(self, config, duration, output):
        """Initialize the vmkstats object"""
        self._config = config
        self._duration = duration
        self._output = output

        self._vdfs_server = None
        self._vdfs_proxy = None

        Logger.info("Creating %s directory", self._output)
        cmd = "mkdir -p %s" % (self._output)
        os.system(cmd)

    def update_vdfs_pids(self):
        """Check for vdfs-server and vdfs-proxy pids in user worlds"""
        for wid in vsi.list("/userworld/cartel"):
            name = vsi.get("/userworld/cartel/%s/cmdline" % wid)
            if re.match(
                r"^/usr/lib/vmware/vdfs/bin/vdfstool --serveronly", name
            ):
                self._vdfs_server = int(wid)
            elif re.match(
                r"^/usr/lib/vmware/vdfs/bin/vdfstool --proxyonly", name
            ):
                self._vdfs_proxy = int(wid)
            if self._vdfs_proxy and self._vdfs_server:
                break

    def enable_vmkstats(self):
        """Enable vmkstats collection"""
        vsi.set("/perf/vmkstats/command/stop", 1)
        vsi.set("/perf/vmkstats/command/config", "remove")
        vsi.set("/perf/vmkstats/command/reset", 1)
        if self._config[0] == "default":
            config = "default"
            vsi.set("/perf/vmkstats/command/config", config)
        else:
            config = "vmkstats unitmask=%s eventsel=%s" % (
                self._config[0],
                self._config[1],
            )
            vsi.set("/perf/vmkstats/command/config", config)
            config = "periodmean=%d" % (self._config[2])
            vsi.set("/perf/vmkstats/command/period", config)

        if self._vdfs_server:
            vsi.set("/perf/vmkstats/command/userstack", self._vdfs_server)
        if self._vdfs_proxy:
            vsi.set("/perf/vmkstats/command/userstack", self._vdfs_proxy)

        vsi.set("/perf/vmkstats/command/start", 1)

    def collect_stats(self, suffix="00:00:00"):
        """Collects stats"""
        output_dir = self._output + "/hcibench_vmkstats_dumpDir" #self._output + "/sub-vmkstats-%s" % suffix
        cmd = "mkdir -p %s" % output_dir
        os.system(cmd)
        time.sleep(self._duration)
        vsi.set("/perf/vmkstats/command/stop", 1)
        vsi.set("/perf/vmkstats/command/drain", 1)
        time.sleep(1)
        # Drain the per-cpu buffers
        cmd = "%s -d" % _VMKSTATSDUMPER_CMD
        os.system(cmd)
        # Dump vmkstats
        cmd = "%s -a -o %s" % (_VMKSTATSDUMPER_CMD, output_dir)
        os.system(cmd)

    def collect_additional_stats(self, suffix="00:00:00"):
        """Collect additional stats"""
        # 1. Collect all the world ids
        output_dir = self._output + "/hcibench_vmkstats_dumpDir" #self._output + "/sub-vmkstats-%s" % suffix
        cmd = "ps -c > %s" % (os.path.join(output_dir, "worlds.txt"))
        os.system(cmd)

        # 2. Collect relevant world ids
        worlds = defaultdict(list)
        for wid in vsi.list("/world"):
            try:
                name = vsi.get("/world/%s/name" % wid)
            except Exception:
                # There could be world without name.
                continue

            for worldName in _WORLD_REGEX_MAP:
                if re.match(_WORLD_REGEX_MAP[worldName], name):
                    worlds[worldName].append(wid)
                    break

            m = re.match(r"vmk(.*)-rx-(.*)", name)
            if m:
                key = "vmk" + m.group(1) + "-rx"
                worlds[key].append(wid)
            m = re.match(r"vmk(.*)-tx", name)
            if m:
                key = "vmk" + m.group(1) + "-tx"
                worlds[key].append(wid)

        if self._vdfs_server:
            worlds["vdfs-server"] = [self._vdfs_server]
        if self._vdfs_proxy:
            worlds["vdfs-proxy"] = [self._vdfs_proxy]
        with open(os.path.join(output_dir, "vsanworlds.json"), "w") as fh:
            fh.write(json.dumps(worlds, indent=2))


def main():
    """Main function to collect vmkstats"""
    opt = optparse.OptionParser()
    opt.add_option("--config", "-c", action="append", default=[])
    opt.add_option(
        "--duration",
        "-d",
        type="int",
        action="store",
        default=60,
        help="stat collection duration in secs",
    )
    opt.add_option("--output", "-o", action="store", help="output directory")
    opt.add_option(
        "--vdfs", action="store_true", default=False, help="enable vdfs pids"
    )
    opt.add_option(
        "--iteration",
        "-i",
        type="int",
        action="store",
        default=1,
        help=" number of times to collect vmkstats",
    )

    opt.add_option(
        "--delay",
        "-w",
        type="int",
        action="store",
        default=0,
        help=" number of seconds to wait to collect vmkstats",
    )

    opt.add_option(
        "--interval",
        "-v",
        type="int",
        action="store",
        default=60,
        help=" number of seconds to wait to collect vmkstats",
    )

    opts, _ = opt.parse_args()

    # Initialize logger
    log_level = logging.DEBUG
    Logger.setLevel(log_level)
    handler = WatchedFileHandler(_LOG_FILE)
    handler.setLevel(log_level)
    Logger.addHandler(handler)

    stats_obj = Vmkstats(opts.config, opts.duration, opts.output)

    if opts.vdfs:
        stats_obj.update_vdfs_pids()

    if opts.duration > 60:
        opts.duration = 60

    if opts.iteration > 6:
        opts.iteration = 6

    if opts.delay > 0:
        time.sleep(opts.delay)

    for i in range(opts.iteration):
        stats_obj.enable_vmkstats()
        suffix = time.strftime("%H-%M-%S")
        stats_obj.collect_stats(suffix)
        stats_obj.collect_additional_stats(suffix)
        if opts.interval > opts.duration:
            time.sleep(opts.interval - opts.duration)


if __name__ == "__main__":
    main()
