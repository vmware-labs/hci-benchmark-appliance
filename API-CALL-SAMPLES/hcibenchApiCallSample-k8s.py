#!/usr/bin/env python3
# hcibenchApiCallSample-k8s.py
# HCIBench API sample for K8s PVC-based testing.
# Compatible with Python 3.6+  |  HCIBench 2.8.1+
#
# Supports:
#   - Standard mode: all fio param files run sequentially, or one selected file.
#     Each pod gets DISK_NUM raw block PVCs mounted at /mnt/pvc0 … /mnt/pvcN-1.
#   - Mixed Workload Mode: multiple pod groups each running a different fio workload
#     in parallel (set USE_MIXED_WORKLOAD = True and populate POD_GROUPS).
#
# K8s testing always uses fio regardless of the TOOL setting.
# Kubeconfig can be supplied as a file path or pasted inline as a string.

import json
import ssl
import time
import urllib.request
from base64 import b64encode

# ---------------------------------------------------------------------------
# Connection settings
# ---------------------------------------------------------------------------
HCIBENCH_IP       = ""          # HCIBench appliance IP or hostname
HCIBENCH_USERNAME = ""          # default: admin
HCIBENCH_PASSWORD = ""

# ---------------------------------------------------------------------------
# Mixed Workload Mode
# Set USE_MIXED_WORKLOAD = True to run different fio workloads on separate pod
# groups simultaneously.  Each group entry needs:
#   "number_vm"  : number of pods in this group (int)
#   "param_file" : filename from /opt/automation/fio-param-files
# When enabled, SELECT_WORKLOAD is ignored and POD_NUM is derived from group totals.
# ---------------------------------------------------------------------------
USE_MIXED_WORKLOAD = False
POD_GROUPS = [
    # {"number_vm": 4, "param_file": "fio-4vmdk-4k-70ws-100rdpct-100randpct-4threads"},
    # {"number_vm": 4, "param_file": "fio-4vmdk-256k-50ws-0rdpct-100randpct-4threads"},
]

# ---------------------------------------------------------------------------
# K8s cluster configuration
# ---------------------------------------------------------------------------
# Provide the kubeconfig via one of two methods:
#   1. KUBECONFIG_PATH  : path to a local kubeconfig file to upload
#   2. KUBECONFIG_CONTENT: paste the full kubeconfig YAML as a string (inline)
# If both are set, KUBECONFIG_CONTENT takes precedence.
KUBECONFIG_PATH    = ""         # e.g. "/root/.kube/config"
KUBECONFIG_CONTENT = ""         # paste kubeconfig YAML inline (alternative)

K8S_NAMESPACE     = "hcibench"  # namespace to create pods and PVCs in
K8S_STORAGE_CLASS = ""          # StorageClass name; "" = use cluster default
# Access mode for PVCs.  Must be one of: ReadWriteOnce, ReadWriteMany, ReadOnlyMany
K8S_ACCESS_MODE   = "ReadWriteOnce"

# Pod / PVC sizing
POD_NUM    = "4"                # total pods; ignored when USE_MIXED_WORKLOAD = True
DISK_NUM   = "4"                # PVCs (raw block devices) per pod
DISK_SIZE  = "100"              # GB per PVC
REUSE_POD  = "true"             # reuse existing pods/PVCs if present

# Run settings
PARAM_FILE_PATH  = "/opt/automation/fio-param-files"
SELECT_WORKLOAD  = ""           # single filename to run; "" = Use All
OUTPUT_PATH      = "K8sTest-Demo"
WARM_UP          = "RANDOM"     # NONE / ZERO / RANDOM
DURATION         = "3600"       # seconds per workload; "0" = use param file value
CLEAN_UP         = "false"      # delete pods/PVCs after testing

# Optional: local param file to upload before configuring
LOCAL_PARAM_FILE = ""           # e.g. "/root/my-workload.fio"


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

    def configure(self, body, kubeconfig_path=None):
        """Configure K8s test.  If kubeconfig_path is given, upload the file."""
        if kubeconfig_path:
            return self._request("generatefile", body, "k8sKubeconfigFile", kubeconfig_path)
        return self._request("generatefile", body)

    def get_param_files(self):
        obj = self._request("getvdbenchparamFile", {"tool": "fio"})
        return obj.get("data", [])

    def upload_param_file(self, param_path):
        obj = self._request("uploadParamfile", {"tool": "fio"}, "paramfile", param_path)
        return "Success" if obj.get("status") == "200" else ("Fail", obj)

    def delete_param_file(self, filename):
        obj = self._request(f"deleteFile?name={filename}&tool=fio")
        return "Success" if obj.get("status") == "200" else ("Fail", obj)

    def prevalidation(self):
        obj = self._request("validatefile")
        data = obj.get("data", "")
        if "All K8s config has been validated" in data:
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

    def cleanup_pods(self):
        """Delete all hcibench pods and PVCs in the configured namespace."""
        obj = self._request("cleanupvms")
        return "Success" if obj.get("status") == "200" else ("Fail", obj)


# ---------------------------------------------------------------------------
# Build request body
# ---------------------------------------------------------------------------
def build_request_body():
    body = {
        "tool":       "fio",            # K8s always uses fio
        "testTarget": "k8s",
        # K8s cluster
        "k8sNamespace":    K8S_NAMESPACE,
        "k8sStorageClass": K8S_STORAGE_CLASS,
        # kubeconfig inline (takes precedence over file upload)
        "k8sKubeconfigContent": KUBECONFIG_CONTENT,
        # Pod / PVC sizing
        "diskNum":   DISK_NUM,
        "diskSize":  DISK_SIZE,
        "reusePod":  REUSE_POD,
        # Run settings
        "filePath":  PARAM_FILE_PATH,
        "outPath":   OUTPUT_PATH,
        "warmUp":    WARM_UP,
        "duration":  DURATION,
        "cleanUp":   CLEAN_UP,
    }

    if USE_MIXED_WORKLOAD and POD_GROUPS:
        # Mixed Workload Mode: total pod count derived from group totals on server side
        body["vmGroups"]      = json.dumps(POD_GROUPS)
        body["selectVdbench"] = ""
    else:
        body["vmNum"]         = POD_NUM
        body["vmGroups"]      = "[]"
        body["selectVdbench"] = SELECT_WORKLOAD

    return body


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    hci = HCIBench(HCIBENCH_IP, HCIBENCH_USERNAME, HCIBENCH_PASSWORD)

    # Optional: upload a workload param file
    if LOCAL_PARAM_FILE:
        print("upload param file:", hci.upload_param_file(LOCAL_PARAM_FILE))

    print("current config:", hci.read_config())
    print("available param files:", hci.get_param_files())

    # Determine how to pass kubeconfig: inline string or file upload
    body = build_request_body()
    if KUBECONFIG_CONTENT:
        # Inline content already included in the body dict
        print("configure (inline kubeconfig):", hci.configure(body))
    elif KUBECONFIG_PATH:
        # Upload kubeconfig as a file; remove the inline key so it doesn't conflict
        body.pop("k8sKubeconfigContent", None)
        print("configure (kubeconfig file):", hci.configure(body, kubeconfig_path=KUBECONFIG_PATH))
    else:
        # Rely on a kubeconfig already saved on the appliance at /opt/automation/conf/kubeconfig
        print("configure (existing kubeconfig on appliance):", hci.configure(body))

    if hci.prevalidation():
        print("start testing:", hci.start_testing())
        while not hci.is_test_finished():
            print("status:\n", hci.read_test_status())
            time.sleep(180)
        print("testing finished")
    else:
        print("pre-validation failed, testing not started")
