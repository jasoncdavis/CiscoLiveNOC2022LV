# version 3
# Refactored to make more modular and read optionsconfig.yaml for inventory
# 2022-0524

from fabric import Connection
import re
import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import sys, os
import threading
import time
import schedule
import math
import datetime
import ReadEnvironmentVars


def get_qfp_data(device):
    cmdoutput = ''
    with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]}) as sshsession:
        cmdoutput = sshsession.run('sh platform hardware qfp active datapath utilization', hide=True).stdout

    #print(cmdoutput)
    regexstr = r'(CPP 0: (Subdev \d).*?Process.*?)\n'
    qfpstats = re.findall(regexstr, cmdoutput, re.S | re.M)
    #print(qfpstats)
    agg_measurements = ''
    for subdev in qfpstats:
        regexstr = r'Processing.*?pct\)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)'
        procload = re.findall(regexstr, subdev[0], re.S | re.M)
        #print(procload)
        instance = subdev[1].replace(" ","\ ")
        agg_measurements += f'wan-stats,metric=qfputil,device={device["alias"]},instance={instance} FiveSec={procload[0][0]},OneMin={procload[0][1]},FiveMin={procload[0][2]},SixtyMin={procload[0][3]}\n'
    #print(agg_measurements)
    return(agg_measurements)



def send_to_influx(influxenv, measurements):
    influxurl = f'{influxenv["protocol"]}://{influxenv["host"]}:{influxenv["port"]}/api/v2/write?bucket={influxenv["influxbucket"]}&org={influxenv["influxorg"]}&precision=s'

    headers = {
    'Accept': 'application/json',
    'Authorization': 'Token ' + influxenv["influxtoken"],
    'Content-Type': 'text/plain'
    }

    response = requests.request("POST", influxurl, headers=headers, data=measurements)
    print(f'{response.status_code} - {response.reason} - {response.text}')

    print(f'Finished at: ' + str(time.ctime()))
    print('\nRunning a sleep loop.', end='', flush=True)


def start_all():
    # Function that reads all target device parameters from project
    # file and calls get_transceiver_data() for each
    devicelist = ReadEnvironmentVars.read_config_file("InterfaceDevices")
    influxenv = ReadEnvironmentVars.read_config_file("InfluxDB")
    agg_measurements = ''
    for device in devicelist:
        print(f"Processing Device instance {device['alias']} {device['host']}...")
        qfpdata = get_qfp_data(device)
        agg_measurements += qfpdata
    print(agg_measurements)
    send_to_influx(influxenv, agg_measurements)


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    print(f'\nRunning thread {threading.current_thread()}')
    job_thread.start() 

print('Starting poll of QFP data')
start_all()    
schedule.every(120).seconds.do(run_threaded, start_all)
print('\nRunning a sleep loop.', end='', flush=True)

try:
    while True:
        print('.', end='', flush=True)
        schedule.run_pending()
        time.sleep(5)
except KeyboardInterrupt:
    print('\nUser initiated stop - closing down process...')
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)
