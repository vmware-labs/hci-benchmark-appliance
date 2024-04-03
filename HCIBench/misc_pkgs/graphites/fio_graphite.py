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

_PROCESS_NAME = "'[f]io -f'"
CARBON_HOST = os.getenv('CARBON_HOST', '127.0.0.1')
CARBON_PORT = os.getenv('CARBON_PORT', 2003)
METRIC_PREFIX = os.getenv('METRIC_PREFIX', 'fio')

#fio still running?
def check_process(pstring):
	pid = ""
	for line in os.popen("ps ax | grep " + pstring + "| grep -v graphite"):
		fields = line.split()
		pid = fields[0]
	if pid != "":
		return True
	else:
		print "fio not running, exiting..."
		return False

def is_json(myjson):
    try:
        json_object = json.loads(myjson)
    except ValueError as e:
        return False
    return True

def parseJson(data):
	try:
		fio_dict = json.loads(data)
	except subprocess.CalledProcessError as err:
		print('{0}: json parse failed ({1})'.format(err))
	return fio_dict

def convertBs(data):
	value = ""
	if data.isdigit():
		value = str(data)
	elif "k" in data or "K" in data:
		value = str(int(''.join(i for i in data if i.isdigit())) * 1024)
	elif "m" in data or "M" in data:
		value = str(int(''.join(i for i in data if i.isdigit())) * 1024 * 1024)
	return value

def to_carbon(data):
	iodepth = 0
	metrics = {}
	timestamp = int(time.time())
	for key, value in data['global options'].items():
		if key == "iodepth":
			iodepth = int(value)
		if key in ["rwmixread","percentage_random"]:
			metrics[key] = value
		if key == "rw" and "read" in value:
			metrics["rwmixread"] = 100
		if key == "rw" and "write" in value:
			metrics["rwmixread"] = 0
		if key == "bs":
			metrics[key] = convertBs(value)
	for job in data['jobs']:
		metrics['cpuload'] = 0
		if 'job options' in job and 'cpuload' in job['job options']:
			metrics['cpuload'] = job['job options']['cpuload']
		if job['read']['bw'] != 0 or job['write']['bw'] != 0:
			for key, value in job['job options'].items():
				if key == "iodepth":
					iodepth = int(value)
				if key in ["rwmixread","percentage_random"]:
					metrics[key] = value
				if key == "rw" and "read" in value:
					metrics["rwmixread"] = 100
				if key == "rw" and "write" in value:
					metrics["rwmixread"] = 0
				if key == "bs":
					metrics[key] = convertBs(value)
			metrics["iodepth"] = iodepth * len(data['disk_util'])
			for key, value in job['read'].items():
				if key in ["bw","iops"]:
					metrics['read.'+key] = value
				if key == "lat_ns":
					metrics['read.'+key] = value["mean"]
					if 'percentile' in value:
						metrics['read.95tile'] = value['percentile']['95.000000']
					else:
						metrics['read.95tile'] = 0
			for key, value in job['write'].items():
				if key in ["bw","iops"]:
					metrics['write.'+key] = value
				if key == "lat_ns":
					metrics['write.'+key] = value["mean"]
					if 'percentile' in value:
						metrics['write.95tile'] = value['percentile']['95.000000']
					else:
						metrics['write.95tile'] = 0
	return metrics

try:
	gService = graphitesend.init(graphite_server=CARBON_HOST,graphite_port=CARBON_PORT,prefix=METRIC_PREFIX)
except Exception as e:
	print "Failed to initiate connection to graphite server:%s on port:%s",(CARBON_HOST,CARBON_PORT)

try:
	file = open(sys.argv[1])
	file.seek(0, os.SEEK_END)
	fulldata = ''
	fio_running = check_process(_PROCESS_NAME)
	count = 0
	while True:
		line = file.readline()
		pos = file.tell()
		if not line:
			if fio_running:
				time.sleep(1)  # wait stdout output to be available
				file.seek(pos)
			else:
				break
			fio_running = check_process(_PROCESS_NAME)
		else:
			count += (line.count("{") - line.count("}"))
			fulldata += line
			if count == 0:
				if is_json(fulldata):
					try:
						fio_data = parseJson(fulldata)
					except:
						print "Fail to parse data as JSON, the data is: " + fulldata
						fulldata = ''
						continue
					else:
						dict_data = to_carbon(fio_data)
					print datetime.datetime.now()
	
					try:
						gService.send_dict(dict_data)
					except Exception as e:
						print e
						print "Failed to send data to graphite server"
					else:
						print dict_data
					finally:
						fulldata = ''
				else:
					print "The following string is not valid JSON format, skip to the end of file: \n" + fulldata
					fulldata = ''
					file.seek(0, os.SEEK_END)
					continue
finally:
	file.close()
