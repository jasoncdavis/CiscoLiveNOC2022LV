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


def get_transceiver_data(device):
    cmdoutput = ''
    with Connection(f'{device["username"]}@{device["host"]}',connect_kwargs={"password": device["password"]}) as sshsession:
        cmdoutput = sshsession.run('show interfaces transceiver', hide=True).stdout

    regexstr = r'(The Transceiver.*?)((?=The)|$)'
    transceivers = re.findall(regexstr, cmdoutput, re.S)
    return(transceivers)


def process_transceiver_data(device, transceiver_data):
    measurements = ''
    for transceiver in transceiver_data:
        regexstr = r'IDPROM for transceiver (.*?):'
        interface = re.search(regexstr, str(transceiver))
        if 'HundredGig' in interface[1]:
            #Get first 4 lanes
            regexstr = r'([TR]x) power Network (Lane\[0[0123]\])\s+=\s+(-*\d+\.\d+) dBm'
            physlanelist = re.findall(regexstr, str(transceiver), re.S | re.M)
            #print(f'{interface[1]} - {physlanelist}')
            for index, tuple in enumerate(physlanelist):
                measurement = f'opticalpower,device={device["alias"]},instance={interface[1]},lane={tuple[0]}{tuple[1]} dBm={tuple[2]}'
                measurements += measurement + '\n'
        elif 'TenGig' in interface[1]:
            #Get single lane
            regexstr = r'Transceiver ([TR]x).*?= (\S+)\s+dBm'
            physlanelist = re.findall(regexstr, str(transceiver), re.S)
            #print(f'{interface[1]} - {physlanelist}')
            for index, tuple in enumerate(physlanelist):
                dbm = tuple[1]
                dbm = dbm.replace('<', '')
                measurement = f'opticalpower,device={device["alias"]},instance={interface[1]},lane={tuple[0]} dBm={dbm}'
                measurements += measurement + '\n'
        else:
            #No match - bail
            pass
    
    #print(repr(measurements))
    return(measurements)


def send_to_influxdb(influxenv, payload):
    print(f'Pushing influx the following payload\n{payload}')
    influxurl = f'{influxenv["protocol"]}://{influxenv["host"]}:{influxenv["port"]}\
/api/v2/write?bucket={influxenv["influxbucket"]}&org={influxenv["influxorg"]}&precision=s'
    #print(influxurl)
    headers = {
    'Accept': 'application/json',
    'Authorization': 'Token ' + influxenv["influxtoken"],
    'Content-Type': 'text/plain'
    }

    response = requests.request("POST", influxurl, headers=headers, data=payload)
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
        transceiver_data = get_transceiver_data(device)
        influx_linedata = process_transceiver_data(device, transceiver_data)
        #print(influx_linedata)
        agg_measurements += influx_linedata
    print(agg_measurements)
    send_to_influx(influxenv, agg_measurements)


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    print(f'\nRunning thread {threading.current_thread()}')
    job_thread.start() 
    
schedule.every(30).seconds.do(run_threaded, start_all)
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
