#!/usr/bin/env python3
# k8s_fio_graphite.py
# Runs on HCIBench appliance. Polls fio JSON output from a K8s pod via
# kubectl exec and sends metrics to the local Graphite (Carbon) on port 2003.
#
# Usage:
#   python3 k8s_fio_graphite.py <kubectl_base> <namespace> <pod_name> \
#          <remote_json_path> <metric_prefix> [poll_interval]
#
# The script polls the remote JSON file every <poll_interval> seconds (default 5),
# parses each complete JSON block (fio --status-interval output), and sends
# metrics to Graphite. It exits when fio is no longer running in the pod.

import sys
import os
import time
import json
import subprocess
import graphitesend
import datetime

def usage():
    print("Usage: k8s_fio_graphite.py <kubectl_base> <namespace> <pod> "
          "<remote_json> <metric_prefix> [poll_interval]")
    sys.exit(1)

if len(sys.argv) < 6:
    usage()

KUBECTL      = sys.argv[1]
NAMESPACE    = sys.argv[2]
POD_NAME     = sys.argv[3]
REMOTE_JSON  = sys.argv[4]
METRIC_PREFIX = sys.argv[5]
POLL_INTERVAL = int(sys.argv[6]) if len(sys.argv) > 6 else 5

CARBON_HOST = "127.0.0.1"
CARBON_PORT = 2003

def kubectl_exec(cmd):
    """Run a command in the pod, return (stdout, returncode)."""
    full_cmd = f"{KUBECTL} exec -n {NAMESPACE} {POD_NAME} -- sh -c {repr(cmd)}"
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=30)
    return result.stdout, result.returncode

def is_fio_running():
    """Check if fio is still running (not zombie) in the pod."""
    # pgrep matches zombies too, so check /proc/<pid>/status for non-zombie state
    out, rc = kubectl_exec("pgrep -x fio")
    if rc != 0 or out.strip() == "":
        return False
    for pid in out.strip().split():
        state_out, _ = kubectl_exec(f"cat /proc/{pid}/status 2>/dev/null | grep -m1 ^State:")
        if state_out and "zombie" not in state_out.lower():
            return True
    return False

def read_remote_file(offset):
    """Read the remote JSON file from the given byte offset. Returns (data, new_offset)."""
    # Use tail -c to skip bytes already read (offset+1 because tail -c + is 1-based)
    cmd = f"tail -c +{offset + 1} {REMOTE_JSON} 2>/dev/null"
    out, rc = kubectl_exec(cmd)
    if rc != 0 or not out:
        return "", offset
    return out, offset + len(out.encode('utf-8'))

def convert_bs(data):
    value = ""
    if data.isdigit():
        value = str(data)
    elif "k" in data.lower():
        value = str(int(''.join(i for i in data if i.isdigit())) * 1024)
    elif "m" in data.lower():
        value = str(int(''.join(i for i in data if i.isdigit())) * 1024 * 1024)
    return value

def to_carbon(data):
    iodepth = 0
    metrics = {}
    for key, value in data.get('global options', {}).items():
        if key == "iodepth":
            iodepth = int(value)
        if key in ["rwmixread", "percentage_random"]:
            metrics[key] = value
        if key == "rw" and "read" in value:
            metrics["rwmixread"] = 100
        if key == "rw" and "write" in value:
            metrics["rwmixread"] = 0
        if key == "bs":
            metrics[key] = convert_bs(value)
    for job in data.get('jobs', []):
        metrics['cpuload'] = 0
        if 'job options' in job and 'cpuload' in job['job options']:
            metrics['cpuload'] = job['job options']['cpuload']
        if job['read']['bw'] != 0 or job['write']['bw'] != 0:
            for key, value in job.get('job options', {}).items():
                if key == "iodepth":
                    iodepth = int(value)
                if key in ["rwmixread", "percentage_random"]:
                    metrics[key] = value
                if key == "rw" and "read" in value:
                    metrics["rwmixread"] = 100
                if key == "rw" and "write" in value:
                    metrics["rwmixread"] = 0
                if key == "bs":
                    metrics[key] = convert_bs(value)
            metrics["iodepth"] = iodepth * len(data.get('disk_util', []))
            for key, value in job['read'].items():
                if key in ["bw", "iops"]:
                    metrics['read.' + key] = value
                if key == "lat_ns":
                    metrics['read.' + key] = value["mean"]
                    if 'percentile' in value:
                        metrics['read.95tile'] = value['percentile']['95.000000']
                    else:
                        metrics['read.95tile'] = 0
            for key, value in job['write'].items():
                if key in ["bw", "iops"]:
                    metrics['write.' + key] = value
                if key == "lat_ns":
                    metrics['write.' + key] = value["mean"]
                    if 'percentile' in value:
                        metrics['write.95tile'] = value['percentile']['95.000000']
                    else:
                        metrics['write.95tile'] = 0
    return metrics

# --- Main loop ---
try:
    g = graphitesend.init(graphite_server=CARBON_HOST, graphite_port=CARBON_PORT,
                          prefix=METRIC_PREFIX, system_name='localhost')
except Exception as e:
    print(f"Failed to connect to graphite: {e}")
    sys.exit(1)

offset = 0
chunks = []
brace_count = 0
fio_running = True

while True:
    new_data, offset = read_remote_file(offset)
    if new_data:
        for ch in new_data:
            chunks.append(ch)
            if ch == '{':
                brace_count += 1
            elif ch == '}':
                brace_count -= 1
                if brace_count == 0 and chunks:
                    fulldata = ''.join(chunks)
                    chunks = []
                    # Complete JSON block
                    try:
                        fio_data = json.loads(fulldata)
                        metrics = to_carbon(fio_data)
                        if metrics:
                            g.send_dict(metrics)
                            print(f"{datetime.datetime.now()} [{POD_NAME}] sent: {metrics}")
                    except json.JSONDecodeError:
                        print(f"Invalid JSON, skipping")
                    except Exception as e:
                        print(f"Failed to send metrics: {e}")
    else:
        # No new data — check if fio is still running
        if not fio_running:
            break
        fio_running = is_fio_running()
        if not fio_running:
            # One final read to catch any remaining data
            new_data, offset = read_remote_file(offset)
            if new_data:
                continue
            break
        time.sleep(POLL_INTERVAL)

print(f"{datetime.datetime.now()} [{POD_NAME}] fio finished, graphite reporter exiting.")
