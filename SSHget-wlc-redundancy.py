# SSHget-wlc-redundancy.py

# Obtains WLC redundancy info (via CLI *sigh*) and puts into InfluxDB
# Version: 1

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
import sendWebexMessage
import ReadEnvironmentVars


def get_redudnancy_stats(wlc_params):
    command = 'show redundancy'

    result = Connection(f'{wlc_params["username"]}@{wlc_params["host"]}',connect_kwargs={"password": wlc_params["password"]}).run(command, hide=True)
    msg = "Ran {0.command!r} on {0.connection.host}, got stdout:\n{0.stdout}"
    #print(msg.format(result))

    regexstr = r'Current Software state = (.*)\r'
    softwarestate = re.findall(regexstr, result.stdout)

    regexstr = r'Available system uptime = (.*)\r'
    systemuptime = re.findall(regexstr, result.stdout)

    regexstr = r'Switchovers system experienced = (\d+)'
    switchovers = re.findall(regexstr, result.stdout)

    regexstr = r'Standby failures = (\d+)'
    standbyfailures = re.findall(regexstr, result.stdout)

    regexstr = r'Last switchover reason = (.*)\r'
    lastswitchoverreason = re.findall(regexstr, result.stdout)

    regexstr = r'Hardware Mode = (.*)\r'
    hardwaremode = re.findall(regexstr, result.stdout)

    regexstr = r'Configured Redundancy Mode = (.*)\r'
    configuredredundancymode = re.findall(regexstr, result.stdout)

    regexstr = r'Operating Redundancy Mode = (.*)\r'
    operatingredundancymode = re.findall(regexstr, result.stdout)

    regexstr = r'Communications = (.*)\r'
    communications = re.findall(regexstr, result.stdout)

    regexstr = r'Uptime in current state = (.*)\r'
    uptimeincurrentstate = re.findall(regexstr, result.stdout)

    return((softwarestate, systemuptime, switchovers, standbyfailures, \
        lastswitchoverreason, hardwaremode, configuredredundancymode, \
        operatingredundancymode, communications, uptimeincurrentstate))

def convert_to_influxline(wlc, measurements):
    fluxline_measurements = ''
    #print(measurements)
    measurement = f'wireless-stats,metric=redundancy,wlc={wlc} \
priswstate="{measurements[0][0].strip()}",\
secswstate="{measurements[0][1].strip()}",\
sysuptime="{measurements[1][0]}",\
switchovers={measurements[2][0]},\
standbyfailures={measurements[3][0]},\
lastswitchoverreason="{measurements[4][0]}",\
hardwaremode="{measurements[5][0]}",\
configuredredundancymode="{measurements[6][0]}",\
operatingredundancymode="{measurements[7][0]}",\
communications="{measurements[8][0]}",\
priuptimeincurrentstate="{measurements[9][0]}",\
secuptimeincurrentstate="{measurements[9][1]}"'
    #print(measurement)
    return(measurement)


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
    

def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    print(f'\nRunning thread {threading.current_thread()}')
    job_thread.start()


def start_all():
    # Function that reads all target device parameters from project
    # file and calls get_wncd() for each
    devicelist = ReadEnvironmentVars.read_config_file("WLC")
    influxenv = ReadEnvironmentVars.read_config_file("InfluxDB")
    aggregatepayload = ''
    for wlc in devicelist:
        print(f"Processing WLC instance {wlc['alias']} {wlc['host']}...")
        redundancystats = get_redudnancy_stats(wlc)
        #print(redundancystats)
        influx_line = convert_to_influxline(wlc['alias'], redundancystats)
        #print(influx_line)
        aggregatepayload += influx_line + '\n'
    #print(aggregatepayload)
    send_to_influxdb(influxenv, aggregatepayload)


start_all()
roomid = ReadEnvironmentVars.read_config_file('wirelessalerts_webexroomid')
sendWebexMessage.sendMessage(roomid,'Starting WLC Redundancy monitoring app...')
schedule.every(60).seconds.do(run_threaded, start_all)
print('\nRunning a sleep loop.', end='', flush=True)

try:
    while True:
        print('.', end='', flush=True)
        schedule.run_pending()
        time.sleep(10)
except KeyboardInterrupt:
    print('\nUser initiated stop - closing down process...')
    sendWebexMessage.sendMessage(roomid,'Stopping WLC Redudnancy monitoring app...')
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)
