#For python2.7, tested with vSphere 7 and vSphere 8
#Compatible with HCIBench 2.8.1+
import mimetools
import mimetypes
import io
import httplib
import json
import os
import time
import socket
import ssl
from base64 import b64encode

class MultiPartForm(object):
    """Accumulate the data to be used when posting a form."""

    def __init__(self):
        self.form_fields = []
        self.files = []
        self.boundary = mimetools.choose_boundary()
        return

    def get_content_type(self):
        return 'multipart/form-data; boundary=%s' % self.boundary

    def add_field(self, name, value):
        """Add a simple field to the form data."""
        self.form_fields.append((name, value))
        return

    def add_file(self, fieldname, filename, fileHandle, mimetype=None):
        """Add a file to be uploaded."""
        body = fileHandle.read()
        if mimetype is None:
            mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        self.files.append((fieldname, filename, mimetype, body))
        return

    def get_binary(self):
        """Return a binary buffer containing the form data, including attached files."""
        part_boundary = '--' + self.boundary
        binary = io.BytesIO()
        needsCLRF = False
        # Add the form fields
        for name, value in self.form_fields:
            if needsCLRF:
                binary.write('\r\n')
            needsCLRF = True

            block = [part_boundary,
              'Content-Disposition: form-data; name="%s"' % name,
              '',
              value
            ]
            binary.write('\r\n'.join(block))

            # Add the files to upload
        for field_name, filename, content_type, body in self.files:
            if needsCLRF:
                binary.write('\r\n')
            needsCLRF = True

            block = [part_boundary,
              str('Content-Disposition: form-data; name="%s"; filename="%s"' % \
              (field_name, filename)),
              'Content-Type: %s' % content_type,
              ''
              ]
            binary.write('\r\n'.join(block))
            binary.write('\r\n')
            binary.write(body)

        # add closing boundary marker,
        binary.write('\r\n--' + self.boundary + '--\r\n')
        return binary

class HCIBench(object):
    def __init__(self,ip, username, password, tool):

        self.userAndPass = b64encode(username+":"+password).decode("ascii")
        self.ip = ip
        self.tool = tool
        self.msg_queue = ""
        return

    def __connectServer__(self, method, restAddr ,request_body={}, file=None, file_field=""):
        form = MultiPartForm()
        if request_body != {}:
            for field, value in request_body.items():
                form.add_field(field, value)
        if file:
            form.add_file(file_field, file.name, file)

        try:
            form_buffer = form.get_binary().getvalue()
            body = form.get_binary().getvalue()
            ctype = form.get_content_type()
            headers = {'Content-Type': ctype, 'Authorization' : 'Basic %s' % self.userAndPass, 'Content-length' : str(len(form_buffer))}
            conn = httplib.HTTPSConnection(self.ip + ":8443", context = ssl._create_unverified_context())
            conn.request(method,'/VMtest/' + restAddr, body, headers)
        except socket.error, e:
            raise SystemExit(1)
        return conn.getresponse()

    #Load the hcibench configuration, aka /opt/automation/conf/perf-conf.yaml
    def read_hcibench_config(self):
        res = self.__connectServer__("POST", "readconfigfile")
        jsonObj = json.loads(res.read())
        return jsonObj

    #Configure hcibench test, aka /opt/automation/conf/perf-conf.yaml
    def configure_hcibench(self, request_body):
        res = self.__connectServer__("POST", "generatefile", request_body)
        jsonObj = json.loads(res.read())
        if jsonObj != {} and jsonObj["status"] == '200':
            return "Success"
        else:
            return "Fail", jsonObj

    #Load parameter files of a given tool
    def get_param_files(self, tool_param=""):
        if tool_param == "":
            tool_selection = {"tool": self.tool}
        else:
            tool_selection = {"tool": tool_param}

        res = self.__connectServer__("POST", "getvdbenchparamFile", tool_selection)
        jsonObj = json.loads(res.read())
        param_files = jsonObj["data"]
        return param_files

    #Configure workload parameter
    def generate_param_file(self, param_body):
        res = self.__connectServer__("POST", "generateParam", param_body)
        jsonObj = json.loads(res.read())
        if jsonObj != {} and jsonObj["status"] == '200':
            name = "%s-%svmdk-%sws-%s-%srdpct-%srandompct-%sthreads" % \
            (param_body["tool"], param_body["diskNum"], param_body["workSet"], param_body["blockSize"], param_body["readPercent"], param_body["randomPercent"], param_body["threadNum"])
            return "Success", name
        else:
            return "Fail", jsonObj

    #Delete a workload parameter file by name
    def delete_param_file(self, filename, tool_param=""):
        if tool_param == "":
            tool_param = self.tool

        res = self.__connectServer__("POST", "deleteFile?name=%s&tool=%s" % (filename,tool_param))
        jsonObj = json.loads(res.read())
        if jsonObj != {} and jsonObj["status"] == '200':
            return "Success"
        else:
            return "Fail", jsonObj

    #Upload a local vdbench zip to HCIBench /opt/output/vdbench-source
    def upload_vdbench_zip(self, vdbench_zip):
        file = open(vdbench_zip, "rb")
        res = self.__connectServer__("POST", "uploadvdbench", {}, file, "vdbenchfile")
        jsonObj = json.loads(res.read())
        if jsonObj["status"] == "200":
            return "Success"
        else:
            return "Fail", jsonObj

    #Upload a local workload parameter file to HCIBench /opt/automation/(vdbench/fio)-param-files
    def upload_param_file(self, param_file):
        file = open(param_file, "rb")
        res = self.__connectServer__("POST", "uploadParamfile", {"tool": self.tool}, file, "paramfile")
        jsonObj = json.loads(res.read())
        if jsonObj["status"] == "200":
            return "Success"
        else:
            return "Fail", jsonObj

    #Kick off prevalidation, return True if success
    def prevalidation(self):
        res = self.__connectServer__("POST", "validatefile")
        jsonObj = json.loads(res.read())

        if "All the config has been validated, please go ahead to kick off testing" in jsonObj["data"]:
            return True
        else:
            print jsonObj["data"]
            return False

    #Start HCIBench testing
    def start_testing(self):
        res = self.__connectServer__("POST", "runtest")
        jsonObj = json.loads(res.read())
        if jsonObj != {} and jsonObj["status"] == '200':
            return "Success"
        else:
            return "Fail", jsonObj

    #Kill HCIBench testing
    def kill_testing(self):
        res = self.__connectServer__("POST", "killtest")
        jsonObj = json.loads(res.read())
        if jsonObj["status"] == "200":
            return "Success"
        else:
            return "Fail", jsonObj

    #Check whether HCIBench testing finished
    def is_test_finished(self):
        res = self.__connectServer__("POST", "istestfinish")
        jsonObj = json.loads(res.read())
        if jsonObj["data"] == '200':
            return True
        else:
            return False

    #Delete guest VMs
    def cleanup_vms(self):
        res = self.__connectServer__("POST", "cleanupvms")
        jsonObj = json.loads(res.read())
        if jsonObj["status"] != '200':
            return "Fail", jsonObj
        else:
            return "Success"

    #Load HCIBench test status
    def read_test_status(self):
        res = self.__connectServer__("GET", "readlog")
        jsonObj = json.loads(res.read())
        if "data" in jsonObj and jsonObj["data"] not in self.msg_queue:
            delta = jsonObj["data"].replace(self.msg_queue.replace('\n...\n',''),'').replace('<br>',"\n")
            self.msg_queue += delta + "\n"
            return self.msg_queue

#fio or vdbench
TOOL = ""

#HCIBench IP and Credential
HCIBench_IP = ""
HCIBench_Username = ""
HCIBench_Password = ""

#full path of local workload parameter file to be uploaded, e.g. /root/home/fio-4vmdk-4k-70ws-100rdpct-100randpct-4threads (OPTIONAL)
workload_param_file_path = ""

#full path of local vdbench zip file to be uploaded, e.g. /root/home/vdbench50407.zip, needed only if you are using vdbench for testing (OPTIONAL)
vdbench_zip_file_path = ""

"""
request_body example:
request_body = {
    "tool": TOOL,
    "vcenterIp": "10.156.12.15",
    "vcenterName": "administrator@vsphere.local",
    "vcenterPwd": "vmware",
    "dcenterName": "paDC",
    "clusterName": "vsanCluster",
    "rpName": "",
    "fdName": "",
    "networkName": "vm-network-vlan30",
    "staticEnabled": "true",
    "staticIpprefix": "172.28",
    "dstoreName": "vsanDatastore",
    "storagePolicy": "perf-policy",
    "deployHost": "false",
    "hosts": "",
    "hostsCredential": "{'host1':{'host_username':'root','host_password':'vmware'}}",
    "clearCache": "true",
    "vsanDebug": "true",
    "reuseVM": "true",
    "easyRun": "false",
    "workloads": "",
    "vmPrefix": "hci-vdb",
    "vmNum": "20",
    "cpuNum": "4",
    "ramSize": "8",
    "diskNum": "8",
    "diskSize": "20",
    "multiWriter": "false",
    "filePath": "/opt/automation/fio-param-files",
    "outPath": "DemoTest",
    "warmUp": "RANDOM",
    "duration": "3600",
    "cleanUp": "false",
    "selectVdbench": "fio-8vmdk-4k-50ws-4thread"
}

"""

request_body = {
    "tool": TOOL,
    #vcenter IP or hostname
    "vcenterIp": "",
    #vcenter admin username
    "vcenterName": "",
    #vcenter admin password
    "vcenterPwd": "",
    #Datacenter Name
    "dcenterName": "",
    #Cluster Name
    "clusterName": "",
    #Resource Pool Name (OPTIONAL)
    "rpName": "",
    #VM Folder Name (OPTIONAL)
    "fdName": "",
    #Network Name (OPTIONAL), if not filled, use "VM Network"
    "networkName": "",
    #set to true if no DHCP in your network, true/false
    "staticEnabled": "",
    #172.16, 172.18, ..., 172.31, 192.168 (OPTIONAL), must be specified if staticEnabled set to true
    "staticIpprefix": "",
    #Name of datastore(s), if you have more datastores to specify, do "datastore1\ndatastor2\ndatastore3
    "dstoreName": "",
    #Storage policy to use (OPTIONAL) if not specified, the datastores' default policy will be used
    "storagePolicy": "",
    #Set to true if you want to deploy VMs onto particular hosts, true/false
    "deployHost": "",
    #Specify the hosts you want to deploy your VMs on (OPTIONAL) "host1\nhost2\nhost3"
    "hosts": "",
    #Clear read/write cache/buffer before each test case, only applicable on vSAN, true/false
    "clearCache": "",
    #vSAN Debug mode, only applicable on vSAN , true/false
    "vsanDebug": "",
    #ESXi hosts credentials, must be specified if clearCache or vsanDebug set to true (OPTIONAL), there are 3 formats:
    # 1.{} -> no need to specify
    # 2.{'':{host_username:root,host_password:password}} -> all the hosts username/password are the same
    # 3.{host_name_1:{host_username:root,host_password:password},host_name_2:{host_username:root,host_password:password}} -> specify credential individually
    "hostsCredential": "",
    #Whether reuse the existing guest VMs if applicable, true/false
    "reuseVM": "",
    #Easy run, only applicable on vSAN, true/false
    "easyRun": "",
    #choose one or multiple from 4k70r, 4k100r, 8k50r, 256k0r, must be specified if easyRun set to true e.g. "4k70r,8k50r"
    "workloads": "",

    #If easy run set to true, no need to fill up the following parameters
    #VM name prefix, no more than 7 chars
    "vmPrefix": "",
    #Number of VMs to deploy
    "vmNum": "",
    #Number of vCPU per VM
    "cpuNum": "",
    #Size of memory per VM
    "ramSize": "",
    #Number of data disks per VM
    "diskNum": "",
    #Size(GB) of each data disk
    "diskSize": "",
    #Whether to use multi-writer VMDK
    "multiWriter": "",
    #Where to find workload param files
    "filePath": "",
    #Test Name, will create a directory /opt/output/results/results20191015144137
    "outPath": "",
    #NONE/ZERO/RANDOM
    "warmUp": "",
    #Testing time (OPTIONAL)
    "duration": "",
    #Whether delete all guest VMs when testing is done, true/false
    "cleanUp": "",
    #The workload param file name, if not specified, will "USE ALL", for either fio or vdbench
    "selectVdbench": ""
}


"""
param_body example:
param_body = {
    "diskNum": "8",
    "workSet": "100",
    "threadNum": "4",
    "blockSize": "4k",
    "readPercent": "70",
    "randomPercent": "100",
    "compRatio": "2", <- vdbench only
    "dedupRatio": "3", <- vdbench only
    "compPct": "40", <- fio only
    "dedupPct": "50", <- fio only
    "ioRate": "", <- read io rate(fio), all io rate(vdbench)
    "ioRateW": "", <- write io rate, fio only
    "testTime": "3600",
    "warmupTime": "1800",
    "intervalTime": "", <- vdbench only
    "cpuUsage": "80", <- fio only
    "latencyTarget": "20000", <- fio only
    "tool": TOOL
}
"""

param_body = {
    #Number of disks will be tested against, 1+ integer, has to be equal or less than diskNum in request_body
    "diskNum": "",
    #Workingset, 1-100 integer
    "workSet": "",
    #Number of threads per VMDK, 1+ integer
    "threadNum": "",
    #Blocksize, "4k", "8k", "1024k"...
    "blockSize": "",
    #Read percentage, 0-100 integer
    "readPercent": "",
    #Random percentage, 0-100 integer
    "randomPercent": "",
    #Compression Ratio for Vdbench, 1+ float (OPTIONAL)
    "compRatio": "",
    #Dedup Ratio for Vdbench, 1+ float (OPTIONAL)
    "dedupRatio": "",
    #Compression Percentage for fio, 0-100 integer (OPTIONAL)
    "compPct": "",
    #Dedup Percentage for fio, 0-100 integer (OPTIONAL)
    "dedupPct": "",
    #for vdbench, it's IO Rate limitaion per VM
    #for fio, it's read IO Rate limiatation per VM
    #1+ integer (OPTIONAL)
    "ioRate": "",
    #fio only, write IO rate limiation per VM, 1+ integer (OPTIONAL)
    "ioRateW": "",
    #Testing time in seconds, 1+ integer
    "testTime": "",
    #Warmup time in seconds, 1+ integer (OPTIONAL)
    "warmupTime": "",
    #for vdbench only, Reporting interval time, 1+ integer (OPTIONAL)
    "intervalTime": "",
    #for fio only, generate CPU load, 0-100 integer (OPTIONAL)
    "cpuUsage": "",
    #for fio only, set latency target in microseconds, 1+ integer (OPTIONAL)
    "latencyTarget": "",
    "tool": TOOL
}

hcibench = HCIBench(HCIBench_IP, HCIBench_Username, HCIBench_Password, TOOL)
#print "upload param: ", hcibench.upload_param_file(workload_param_file_path)
#print "upload zip: ", hcibench.upload_vdbench_zip(vdbench_zip_file_path)
print "read config: ", hcibench.read_hcibench_config()

#Here we will delete the file named "abc" in /opt/automation/TOOL[vdbench/fio]-param-files
#print "delete workload param: ", hcibench.delete_param_file('abc', TOOL)
print "get param files: ", hcibench.get_param_files(TOOL)
print "kill testing: ", hcibench.kill_testing()
#print "delete vms: ", hcibench.cleanup_vms()
print "generate param file: ", hcibench.generate_param_file(param_body)
print "configure hcibench: ", hcibench.configure_hcibench(request_body)
if hcibench.prevalidation():
    print "start testing: ", hcibench.start_testing()
    while not hcibench.is_test_finished():
        print "hcibench testing status: ", hcibench.read_test_status()
        time.sleep(180)