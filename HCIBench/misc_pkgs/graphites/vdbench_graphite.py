import fcntl
import time
import os
import shlex
import subprocess
import graphitesend
import datetime
import sys
import json
import re

_PROCESS_NAME = "'[v]dbench -f'"
CARBON_HOST = os.getenv('CARBON_HOST', '127.0.0.1')
CARBON_PORT = os.getenv('CARBON_PORT', 2003)
METRIC_PREFIX = os.getenv('METRIC_PREFIX', 'vdbench')
title_list = []
metrics = {}

#vdbench still running?
def check_process(pstring):
    pid = ""
    for line in os.popen("ps ax | grep " + pstring + "| grep -v graphite"):
        fields = line.split()
        pid = fields[0]
    if pid != "":
        return True
    else:
        print "vdbench not running, exiting..."
        return False

try:
    gService = graphitesend.init(graphite_server=CARBON_HOST, graphite_port=CARBON_PORT, prefix=METRIC_PREFIX)
except Exception as e:
    print "Failed to initiate connection to graphite server:%s on port:%s",(CARBON_HOST,CARBON_PORT)

try:
    file = open(sys.argv[1])
    file.seek(0, os.SEEK_END)
    fulldata = ''
    vdbench_running = check_process(_PROCESS_NAME)
    count = 0
    while True:
        line = file.readline()
        pos = file.tell()
        if not line:
            if vdbench_running:
                #time.sleep(1)  # wait stdout output to be available, may not needed for vdbench
                file.seek(pos)
            else:
                break
            vdbench_running = check_process(_PROCESS_NAME)
        else:
            param_array = list(map(lambda st: str.replace(st, "+", "_"),line.split()))
            #make up title list, one-off action
            if title_list == [] and len(param_array) > 4 and param_array[3] == "interval":
                title_list = param_array[4:]
            if title_list != [] and title_list[0] == "i/o" and len(param_array) > 4 and param_array[0] == "rate":
                title_list = map(lambda x, y: x + " " + y, title_list, param_array)
            print "title_list:", title_list

            #real stuff for numbers!
            if not re.search('[a-zA-Z]', line) and len(param_array) != 0:
                data_list = param_array[2:]
                print "data_list:",data_list
                if len(title_list) == len(data_list):
                    for title_index in range(len(title_list)):
                        print "title_index:",title_index
                        title = title_list[title_index]
                        number = data_list[title_index]
                        metrics[title] = number
                    print datetime.datetime.now()
                try:
                    gService.send_dict(metrics)
                except Exception as e:
                    print e
                    print "Failed to send data to graphite server"
                else:
                    print metrics
                finally:
                    metrics = {}
finally:
    file.close()
