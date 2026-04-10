#!/usr/bin/env python3
# hcibenchApiCallSample-vm.py
# HCIBench API sample for VM-based (vSphere) testing.
# Compatible with Python 3.6+  |  HCIBench 2.8.1+
#
# Supports:
#   - Standard mode: all param files run sequentially, or one selected file
#   - Mixed Workload Mode: multiple VM groups each running a different workload
#     in parallel (set USE_MIXED_WORKLOAD = True and populate VM_GROUPS)

import json
import ssl
import time
import urllib.request
import urllib.parse
from base64 import b64encode

# ---------------------------------------------------------------------------
# Connection settings
# ---------------------------------------------------------------------------
HCIBENCH_IP       = ""          # HCIBench appliance IP or hostname
HCIBENCH_USERNAME = ""          # default: admin
HCIBENCH_PASSWORD = ""

# ---------------------------------------------------------------------------
# Tool selection
# ---------------------------------------------------------------------------
TOOL = "fio"                    # "fio" or "vdbench"

# ---------------------------------------------------------------------------
# Mixed Workload Mode
# Set USE_MIXED_WORKLOAD = True to run different workloads on separate VM groups
# simultaneously.  Each group entry needs:
#   "number_vm"  : number of VMs in this group (int)
#   "param_file" : filename from /opt/automation/fio-param-files (or vdbench)
# When enabled, SELECT_WORKLOAD is ignored.
# ---------------------------------------------------------------------------
USE_MIXED_WORKLOAD = False
VM_GROUPS = [
    # {"number_vm": 4, "param_file": "fio-4vmdk-4k-70ws-100rdpct-100randpct-4threads"},
    # {"number_vm": 4, "param_file": "fio-4vmdk-256k-50ws-0rdpct-100randpct-4threads"},
]

# ---------------------------------------------------------------------------
# vSphere / VM configuration
# ---------------------------------------------------------------------------
VCENTER_IP        = ""
VCENTER_USERNAME  = "administrator@vsphere.local"
VCENTER_PASSWORD  = ""
DATACENTER_NAME   = ""
CLUSTER_NAME      = ""
RESOURCE_POOL     = ""          # optional
VM_FOLDER         = ""          # optional
NETWORK_NAME      = ""          # defaults to "VM Network" if empty
DATASTORE_NAME    = ""          # multiple: "ds1\nds2\nds3"
STORAGE_POLICY    = ""          # optional; uses datastore default if empty

# Static IP settings (set STATIC_ENABLED="true" if no DHCP)
STATIC_ENABLED    = "false"
STATIC_IP_PREFIX  = ""         # e.g. "172.16", required when static_enabled=true

# Hosts settings
DEPLOY_ON_HOSTS   = "false"
HOSTS             = ""         # e.g. "host1\nhost2"
HOSTS_CREDENTIAL  = "{}"       # "{}" or "{'':{'host_username':'root','host_password':'pass'}}"

# Cache / debug (vSAN only)
CLEAR_CACHE  = "true"
VSAN_DEBUG   = "true"

# VM sizing
VM_PREFIX    = "hci-fio"       # ≤ 7 characters
VM_NUM       = "4"             # ignored when USE_MIXED_WORKLOAD = True
CPU_NUM      = "4"
RAM_SIZE     = "8"             # GB
DISK_NUM     = "4"             # data disks per VM
DISK_SIZE    = "100"           # GB per disk
MULTI_WRITER = "false"

# Run settings
REUSE_VM      = "true"
EASY_RUN      = "false"
WORKLOADS     = "null"         # easy run workload keys, comma-separated; ignored when EASY_RUN=false
LATENCY_TARGET = "Low"         # Max / Low / Medium / High
PARAM_FILE_PATH = "/opt/automation/fio-param-files"
SELECT_WORKLOAD  = ""          # filename to run; "" = Use All (ignored in Mixed Workload Mode)
OUTPUT_PATH   = "VMTest-Demo"
WARM_UP       = "RANDOM"       # NONE / ZERO / RANDOM
DURATION      = "3600"         # seconds; "0" = use param file value
CLEAN_UP      = "false"

# Optional local files to upload before configuring
LOCAL_PARAM_FILE  = ""         # full path, e.g. "/root/my-workload.fio"
LOCAL_VDBENCH_ZIP = ""         # full path, e.g. "/root/vdbench50407.zip"


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------
class HCIBench:
    def __init__(self, ip, username, password):
        token = b64encode(f"{username}:{password}".encode()).decode()
        self._auth = f"Basic {token}"
        self._base = f"https://{ip}:8443/VMtest"
        self._ctx  = ssl._create_unverified_context()
        self._msg_queue = ""

    def _request(self, endpoint, fields=None, file_field=None, file_path=None, method="POST"):
        """Multipart POST (or plain GET when method='GET')."""
        if method == "GET":
            req = urllib.request.Request(
                f"{self._base}/{endpoint}",
                headers={"Authorization": self._auth},
                method="GET",
            )
            with urllib.request.urlopen(req, context=self._ctx) as resp:
                return json.loads(resp.read())

        boundary = "HCIBenchBoundary"
        body_parts = []

        for name, value in (fields or {}).items():
            body_parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n".encode()
            )

        if file_path and file_field:
            filename = file_path.split("/")[-1]
            with open(file_path, "rb") as fh:
                file_data = fh.read()
            body_parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
                f"Content-Type: application/octet-stream\r\n\r\n".encode()
                + file_data + b"\r\n"
            )

        body_parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(
            p if isinstance(p, bytes) else p.encode() for p in body_parts
        )

        req = urllib.request.Request(
            f"{self._base}/{endpoint}",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": self._auth,
                "Content-Length": str(len(body)),
            },
            method="POST",
        )
        with urllib.request.urlopen(req, context=self._ctx) as resp:
            return json.loads(resp.read())

    def read_config(self):
        return self._request("readconfigfile")

    def configure(self, body):
        obj = self._request("generatefile", body)
        return "Success" if obj.get("status") == "200" else ("Fail", obj)

    def get_param_files(self):
        obj = self._request("getvdbenchparamFile", {"tool": TOOL})
        return obj.get("data", [])

    def generate_param_file(self, param_body):
        obj = self._request("generateParam", param_body)
        if obj.get("status") == "200":
            name = (
                "{tool}-{diskNum}vmdk-{workSet}ws-{blockSize}-"
                "{readPercent}rdpct-{randomPercent}randompct-{threadNum}threads"
            ).format(**param_body)
            return "Success", name
        return "Fail", obj

    def delete_param_file(self, filename):
        obj = self._request(f"deleteFile?name={filename}&tool={TOOL}")
        return "Success" if obj.get("status") == "200" else ("Fail", obj)

    def upload_vdbench_zip(self, zip_path):
        obj = self._request("uploadvdbench", {}, "vdbenchfile", zip_path)
        return "Success" if obj.get("status") == "200" else ("Fail", obj)

    def upload_param_file(self, param_path):
        obj = self._request("uploadParamfile", {"tool": TOOL}, "paramfile", param_path)
        return "Success" if obj.get("status") == "200" else ("Fail", obj)

    def prevalidation(self):
        obj = self._request("validatefile")
        data = obj.get("data", "")
        if "All the config has been validated" in data:
            return True
        print("Pre-validation output:\n", data)
        return False

    def start_testing(self):
        obj = self._request("runtest")
        return "Success" if obj.get("status") == "200" else ("Fail", obj)

    def kill_testing(self):
        obj = self._request("killtest")
        return "Success" if obj.get("status") == "200" else ("Fail", obj)

    def is_test_finished(self):
        obj = self._request("istestfinish")
        return obj.get("data") == "200"

    def read_test_status(self):
        obj = self._request("readlog", method="GET")
        if "data" in obj and obj["data"] not in self._msg_queue:
            delta = obj["data"].replace(self._msg_queue.replace("\n...\n", ""), "").replace("<br>", "\n")
            self._msg_queue += delta + "\n"
        return self._msg_queue

    def cleanup_vms(self):
        obj = self._request("cleanupvms")
        return "Success" if obj.get("status") == "200" else ("Fail", obj)


# ---------------------------------------------------------------------------
# Build request body
# ---------------------------------------------------------------------------
def build_request_body():
    body = {
        "tool":           TOOL,
        "testTarget":     "vm",
        # vSphere connection
        "vcenterIp":      VCENTER_IP,
        "vcenterName":    VCENTER_USERNAME,
        "vcenterPwd":     VCENTER_PASSWORD,
        "dcenterName":    DATACENTER_NAME,
        "clusterName":    CLUSTER_NAME,
        "rpName":         RESOURCE_POOL,
        "fdName":         VM_FOLDER,
        "networkName":    NETWORK_NAME,
        "dstoreName":     DATASTORE_NAME,
        "storagePolicy":  STORAGE_POLICY,
        # Static IP
        "staticEnabled":  STATIC_ENABLED,
        "staticIpprefix": STATIC_IP_PREFIX,
        # Hosts
        "deployHost":     DEPLOY_ON_HOSTS,
        "hosts":          HOSTS,
        "hostsCredential": HOSTS_CREDENTIAL,
        # vSAN
        "clearCache":     CLEAR_CACHE,
        "vsanDebug":      VSAN_DEBUG,
        # VM sizing
        "vmPrefix":       VM_PREFIX,
        "cpuNum":         CPU_NUM,
        "ramSize":        RAM_SIZE,
        "diskNum":        DISK_NUM,
        "diskSize":       DISK_SIZE,
        "multiWriter":    MULTI_WRITER,
        # Run settings
        "reuseVM":        REUSE_VM,
        "easyRun":        EASY_RUN,
        "workloads":      WORKLOADS,
        "latencyTarget":  LATENCY_TARGET,
        "filePath":       PARAM_FILE_PATH,
        "outPath":        OUTPUT_PATH,
        "warmUp":         WARM_UP,
        "duration":       DURATION,
        "cleanUp":        CLEAN_UP,
    }

    if USE_MIXED_WORKLOAD and VM_GROUPS:
        # Mixed Workload Mode: vmNum is derived from group totals by the server
        body["vmGroups"]      = json.dumps(VM_GROUPS)
        body["selectVdbench"] = ""
    else:
        body["vmNum"]         = VM_NUM
        body["vmGroups"]      = "[]"
        body["selectVdbench"] = SELECT_WORKLOAD

    return body


# ---------------------------------------------------------------------------
# Example param body (fio)
# ---------------------------------------------------------------------------
PARAM_BODY = {
    "tool":          TOOL,
    "diskNum":       "4",       # disks to test, ≤ diskNum in request body
    "workSet":       "100",     # working set %, 1-100
    "threadNum":     "4",       # threads per disk
    "blockSize":     "4k",
    "readPercent":   "70",      # 0-100
    "randomPercent": "100",     # 0-100
    "compPct":       "0",       # fio: compression %, 0-100 (optional)
    "dedupPct":      "0",       # fio: dedup %, 0-100 (optional)
    "ioRate":        "",        # fio: read IOPS limit per VM (optional)
    "ioRateW":       "",        # fio: write IOPS limit per VM (optional)
    "testTime":      "3600",
    "warmupTime":    "300",     # optional
    "cpuUsage":      "",        # fio: CPU load target 0-100 (optional)
    "latencyTarget": "",        # fio: latency target in µs (optional)
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    hci = HCIBench(HCIBENCH_IP, HCIBENCH_USERNAME, HCIBENCH_PASSWORD)

    # Optional: upload a workload param file
    if LOCAL_PARAM_FILE:
        print("upload param file:", hci.upload_param_file(LOCAL_PARAM_FILE))

    # Optional: upload vdbench zip (only needed when TOOL = "vdbench")
    if LOCAL_VDBENCH_ZIP:
        print("upload vdbench zip:", hci.upload_vdbench_zip(LOCAL_VDBENCH_ZIP))

    print("current config:", hci.read_config())
    print("available param files:", hci.get_param_files())

    # Optional: generate a new param file from scratch
    # print("generate param file:", hci.generate_param_file(PARAM_BODY))

    print("configure:", hci.configure(build_request_body()))

    if hci.prevalidation():
        print("start testing:", hci.start_testing())
        while not hci.is_test_finished():
            print("status:\n", hci.read_test_status())
            time.sleep(180)
        print("testing finished")
    else:
        print("pre-validation failed, testing not started")
